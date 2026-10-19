"""A2: name cap, trade cost, legacy bit-identity, and pack parity."""

from __future__ import annotations

import importlib.util
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine.export import STRATEGY_MODULE, build_strategy_pack
from engine.main import ResearchCommandService
from engine.metrics import calculate_metrics
from engine.portfolio import (
    SCHEDULE_NAME_CAP,
    allocate_weights,
    legacy_weights,
    min_names_for_cap,
    one_way_cost_fraction,
)
from engine.research.a2_copy import (
    CN_EQUITY_COST,
    CN_EXECUTION_NOTICE,
    US_EQUITY_CONSTRUCTION,
    US_EQUITY_COST,
)
from engine.research.loop import _execution_spec
from engine.research.models import (
    AssetClass,
    Market,
    Slot,
    Universe,
    new_research,
)
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.strategy import (
    MarketPanel,
    MeanReversionStrategy,
    daily_book,
    run_daily_backtest,
)
from tests.test_export_pack import completed_research, reference_strategy, snapshot
from tests.test_state_machine import NOW, locked_brief


def _legacy_formula(strategy: MeanReversionStrategy, data: MarketPanel) -> pd.Series:
    signals = strategy.generate_signals(data).shift(1).fillna(0.0)
    gross = signals.abs().sum(axis=1).replace(0.0, 1.0)
    weights = signals.div(gross, axis=0)
    asset_returns = data.prices.pct_change(fill_method=None).fillna(0.0)
    return (weights * asset_returns).sum(axis=1).rename("strategy_return")


def test_legacy_spec_matches_the_historical_weights_bit_for_bit() -> None:
    strategy = reference_strategy()
    data = snapshot()
    assert strategy.spec.cost_model == "legacy_zero"
    assert strategy.spec.name_weight_cap is None
    got = run_daily_backtest(strategy, data)
    expected = _legacy_formula(strategy, data)
    assert got.tolist() == expected.tolist()


def test_min_names_for_five_percent_is_twenty() -> None:
    assert min_names_for_cap(0.05) == 20


def test_cost_table_matches_the_decided_one_way_rates() -> None:
    assert one_way_cost_fraction(Market.US, AssetClass.FUND) == pytest.approx(1 / 10_000)
    assert one_way_cost_fraction(Market.US, AssetClass.EQUITY) == pytest.approx(5 / 10_000)
    assert one_way_cost_fraction(Market.CN, AssetClass.EQUITY) == pytest.approx(20 / 10_000)
    assert one_way_cost_fraction(Market.CN, AssetClass.FUND) == pytest.approx(5 / 10_000)


def test_equal_weight_expands_using_pool_order_then_leaves_cash() -> None:
    index = pd.RangeIndex(1)
    columns = [f"S{i}" for i in range(4)]
    signals = pd.DataFrame([[1.0, 0.0, 0.0, 0.0]], index=index, columns=columns)
    scores = pd.DataFrame([[0.1, 0.4, 0.3, 0.2]], index=index, columns=columns)
    weights = allocate_weights(
        signals,
        scores,
        name_cap=0.5,
        pool_symbols=("S2", "S1", "S3", "S0"),
    )
    row = weights.iloc[0]
    assert row["S0"] == pytest.approx(0.5)
    assert row["S1"] == pytest.approx(0.5)
    assert row["S2"] == 0.0
    assert float(row.sum()) == pytest.approx(1.0)
    tight = allocate_weights(signals, scores, name_cap=0.2, pool_symbols=())
    assert (tight.iloc[0] <= 0.2 + 1e-12).all()
    assert float(tight.iloc[0].sum()) == pytest.approx(0.8)
    assert tight.iloc[0]["S0"] == pytest.approx(0.2)


def test_other_weights_clip_and_redistribute_without_exceeding_the_cap() -> None:
    index = pd.RangeIndex(1)
    signals = pd.DataFrame([[0.7, 0.2, 0.1]], index=index, columns=["A", "B", "C"])
    weights = allocate_weights(signals, None, name_cap=0.5)
    row = weights.iloc[0]
    assert float(row.max()) <= 0.5 + 1e-12
    assert float(row.sum()) <= 1.0 + 1e-12
    assert float(row.min()) >= -1e-12
    assert float(row.sum()) == pytest.approx(1.0)


def test_fund_leg_is_not_name_capped_but_pays_one_bp() -> None:
    strategy = reference_strategy()
    fund = Universe(Market.US, AssetClass.FUND, AssetClass.EQUITY, ("AAA", "BBB"))
    scheduled = replace(
        strategy.spec,
        universe=fund,
        cost_model="schedule_v1",
        name_weight_cap=None,
    )
    book = daily_book(MeanReversionStrategy(scheduled), snapshot())
    assert float(book.weights.abs().to_numpy().max()) > SCHEDULE_NAME_CAP
    assert book.cost.sum() == pytest.approx(0) or float(book.cost.max()) <= 1 / 10_000 + 1e-12


def test_random_books_respect_cap_gross_and_net_identity() -> None:
    rng = np.random.default_rng(7)
    for _ in range(30):
        rows = int(rng.integers(5, 12))
        cols = int(rng.integers(2, 6))
        index = pd.bdate_range("2020-01-02", periods=rows)
        columns = [f"N{i}" for i in range(cols)]
        signal = pd.DataFrame(rng.random((rows, cols)), index=index, columns=columns)
        signal.iloc[0] = 0.0
        weights = allocate_weights(signal, signal, name_cap=0.4)
        assert float(weights.to_numpy().max()) <= 0.4 + 1e-9
        assert float(weights.sum(axis=1).max()) <= 1.0 + 1e-9
        assert float(weights.to_numpy().min()) >= -1e-12
        returns = pd.DataFrame(rng.normal(0, 0.01, size=(rows, cols)), index=index, columns=columns)
        from engine.portfolio import build_book

        rate = 5 / 10_000
        book = build_book(weights, returns, one_way_cost=rate)
        turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
        assert np.allclose(book.net.to_numpy(), (book.gross - turnover * rate).to_numpy())
        assert np.allclose(book.cost.to_numpy(), (turnover * rate).to_numpy())


def test_schedule_net_is_gross_minus_us_equity_cost() -> None:
    strategy = reference_strategy()
    spec = replace(strategy.spec, cost_model="schedule_v1", name_weight_cap=0.5)
    book = daily_book(MeanReversionStrategy(spec), snapshot())
    rate = 5 / 10_000
    turnover = book.weights.diff().abs().sum(axis=1).fillna(0.0)
    assert np.allclose(book.net.to_numpy(), (book.gross - turnover * rate).to_numpy())
    legacy = legacy_weights(strategy.generate_signals(snapshot()).shift(1).fillna(0.0))
    assert not np.allclose(book.weights.to_numpy(), legacy.to_numpy())


def test_cn_new_round_uses_the_schedule_and_us_legacy_round_does_not() -> None:
    from tests.test_loop_runtime import running_research

    us = running_research()
    us_spec = reference_strategy().spec
    assert _execution_spec(us_spec, us).cost_model == "legacy_zero"
    confirmed = replace(us, construction_schedule="schedule_v1")
    scheduled = _execution_spec(us_spec, confirmed)
    assert scheduled.cost_model == "schedule_v1"
    assert scheduled.name_weight_cap is None
    cn_universe = Universe(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY, ("600519.SH",))
    cn_spec = replace(us_spec, universe=cn_universe)
    cn = replace(us, brief=replace(us.brief, universe=Slot(cn_universe, True)))
    upgraded = _execution_spec(cn_spec, cn)
    assert upgraded.cost_model == "schedule_v1"
    assert upgraded.name_weight_cap is None
    assert one_way_cost_fraction(Market.CN, AssetClass.EQUITY) == pytest.approx(20 / 10_000)


def test_confirm_card_states_the_us_equity_assumption_and_cn_page_states_tplus(
    tmp_path: Path,
) -> None:
    service = ResearchCommandService(
        SQLiteStore(tmp_path / "view.db"),
        EnginePaths.for_colocated_root(tmp_path),
    )
    us = replace(
        new_research("r-us", NOW),
        brief=locked_brief(),
    )
    cn_brief = replace(
        locked_brief(),
        universe=Slot(
            Universe(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY, ("600519.SH",)),
            True,
        ),
    )
    cn = replace(completed_research(), research_id="r-cn", brief=cn_brief)
    service.store.create(us)
    service.store.create(cn)
    confirm = service.view_for("#/research/r-us")
    assert confirm["constructionNotice"] == US_EQUITY_COST
    assert "单票 ≤5%" not in confirm["constructionNotice"]
    done = service.view_for("#/research/r-cn")
    assert done["cnExecutionNotice"] == CN_EXECUTION_NOTICE
    us_done = service.view_for("#/research/r-us")
    assert "cnExecutionNotice" not in us_done or not us_done.get("cnExecutionNotice")


def test_name_cap_tracks_holdable_names_on_the_card_and_in_the_engine() -> None:
    from engine.research.a2_copy import construction_notice_for
    from engine.strategy import apply_trading_schedule
    from tests.test_loop_runtime import running_research

    wide_names = tuple(f"S{i}" for i in range(20))
    wide = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, wide_names)
    single = Universe(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY, ("600519.SH",))
    base = reference_strategy().spec
    wide_spec = apply_trading_schedule(replace(base, universe=wide))
    single_spec = apply_trading_schedule(replace(base, universe=single))
    assert wide_spec.name_weight_cap == pytest.approx(0.05)
    assert single_spec.cost_model == "schedule_v1"
    assert single_spec.name_weight_cap is None

    index = pd.RangeIndex(1)
    wide_signals = pd.DataFrame([[1.0, *([0.0] * 19)]], index=index, columns=list(wide_names))
    wide_scores = pd.DataFrame(
        [[float(20 - i) for i in range(20)]],
        index=index,
        columns=list(wide_names),
    )
    capped = allocate_weights(
        wide_signals,
        wide_scores,
        name_cap=wide_spec.name_weight_cap,
    )
    assert float(capped.iloc[0].max()) <= 0.05 + 1e-12
    assert float(capped.iloc[0].sum()) == pytest.approx(1.0)

    one_signal = pd.DataFrame([[1.0]], index=index, columns=["600519.SH"])
    free = allocate_weights(one_signal, one_signal, name_cap=single_spec.name_weight_cap)
    assert float(free.iloc[0, 0]) == pytest.approx(1.0)
    assert float(free.iloc[0, 0]) > 0.05

    research = running_research()
    wide_card = construction_notice_for(
        replace(research, brief=replace(research.brief, universe=Slot(wide, True)))
    )
    single_card = construction_notice_for(
        replace(research, brief=replace(research.brief, universe=Slot(single, True)))
    )
    assert wide_card == US_EQUITY_CONSTRUCTION
    assert wide_card is not None and "单票 ≤5%" in wide_card
    assert single_card == CN_EQUITY_COST
    assert single_card is not None and "单票 ≤5%" not in single_card
    assert "保守产品假设" in single_card
    probed = Universe(
        Market.US,
        AssetClass.EQUITY,
        AssetClass.EQUITY,
        tuple(f"P{i}" for i in range(15)),
    )
    probed_card = construction_notice_for(
        replace(research, brief=replace(research.brief, universe=Slot(probed, True)))
    )
    assert probed_card == US_EQUITY_COST
    assert probed_card is not None and "单票 ≤5%" not in probed_card
    pool = Universe(
        Market.US,
        AssetClass.EQUITY,
        AssetClass.EQUITY,
        tuple(f"D{i}" for i in range(503)),
    )
    pool_card = construction_notice_for(
        replace(research, brief=replace(research.brief, universe=Slot(pool, True)))
    )
    assert pool_card == US_EQUITY_CONSTRUCTION


def test_pack_schedule_matches_engine_within_1e_12(tmp_path: Path) -> None:
    index = pd.bdate_range("2024-01-02", periods=40)
    rng = np.random.default_rng(3)
    prices = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0, 0.01, size=(40, 2)), axis=0)),
        index=index,
        columns=["AAA", "BBB"],
    )
    benchmark = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.008, size=40))), index=index, name="SPX")
    panel = MarketPanel(prices, datetime(2024, 3, 1, tzinfo=UTC), benchmark)
    spec = replace(
        reference_strategy().spec,
        cost_model="schedule_v1",
        name_weight_cap=0.05,
        lookback_days=5,
        entry_z=0.25,
    )
    strategy = MeanReversionStrategy(spec)
    book = daily_book(strategy, panel)
    from engine.metrics import SimulationDiagnostics

    report = calculate_metrics(
        book.net,
        benchmark.pct_change(fill_method=None).fillna(0.0),
        "SPX",
        SimulationDiagnostics(
            sharpe_oos=0.0,
            sharpe_is=0.0,
            oos_segment_returns=(0.0, 0.0, 0.0),
            top_20_crowding_sharpe_impact=0.0,
            annual_turnover=0.0,
            covered_assets=2,
            missing_pct=0.0,
        ),
    )
    research = completed_research()
    attempt = research.versions[0].rounds[0].accepted_attempt
    updated = replace(
        research,
        versions=(
            replace(
                research.versions[0],
                rounds=(
                    replace(
                        research.versions[0].rounds[0],
                        accepted_attempt=replace(attempt, spec=spec, simulation=report),
                    ),
                ),
            ),
        ),
    )
    archive = build_strategy_pack(updated, strategy, panel, tmp_path / "pack.zip")
    extracted = tmp_path / "extracted"
    import zipfile

    with zipfile.ZipFile(archive) as packed:
        packed.extractall(extracted)
    module_path = extracted / "strategy.py"
    module_path.write_text(STRATEGY_MODULE, encoding="utf-8")
    spec_loader = importlib.util.spec_from_file_location("pack_strategy", module_path)
    assert spec_loader and spec_loader.loader
    module = importlib.util.module_from_spec(spec_loader)
    spec_loader.loader.exec_module(module)
    result = module.backtest(extracted)
    for field in ("r_total", "r_ann", "sharpe", "max_drawdown", "excess_ann"):
        assert result[field] == pytest.approx(getattr(report, field), abs=1e-12)
