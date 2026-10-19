"""A1: family registry fields, confirm class, and one frozen input panel per version."""

from __future__ import annotations

import socket
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from engine.main import ResearchCommandService, build_loop
from engine.research.clock import TimeBudget
from engine.research.data_port import data_port_for_research
from engine.research.gather import RoutingDataAdapter
from engine.research.loop import DefaultRoundBuilder, ResearchLoop
from engine.research.models import (
    AssetClass,
    ChangeClass,
    ConfirmKind,
    CoverageFloor,
    Market,
    MethodRef,
    ResearchEvent,
    ResearchStatus,
    Slot,
    Universe,
    new_research,
)
from engine.research.pool_data_shrink import set_pool_data_loader, symbols_with_daily_data
from engine.research.runtime import EnginePaths
from engine.research.specify import ProposedChange, classify_change
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError
from engine.review.deterministic import DeterministicReviewer, default_v1_pass
from engine.strategy import MeanReversionStrategy, StrategySpec, run_daily_backtest
from tests.test_deterministic_reviewer import _draft, _spec
from tests.test_export_pack import completed_research, snapshot
from tests.test_honest_stop import change_requires_user_confirm
from tests.test_loop_runtime import (
    NOW,
    FailedMethodsParamBuilder,
    PassReviewer,
    running_research,
)

PIN_START = date(2014, 1, 2)
PIN_END = date(2016, 12, 30)
PROCESS_START = date(2020, 1, 1)
PROCESS_END = date(2021, 1, 1)


def test_family_primary_factor_and_lineage_changes_need_confirm() -> None:
    family = ProposedChange("strategy_family", "mean_reversion", "low_volatility")
    factor = ProposedChange("primary_factor", None, "value")
    proxy = ProposedChange("proxy", "AGG", "IEF")
    binding = ProposedChange("data_bindings", (), ("local-csv",))
    source = ProposedChange("data_source_id", "yahoo_daily", "local_file")

    assert classify_change(family) is ChangeClass.ECONOMIC
    assert classify_change(factor) is ChangeClass.ECONOMIC
    assert classify_change(proxy).value == "data_lineage"
    assert classify_change(binding).value == "data_lineage"
    assert classify_change(source).value == "data_lineage"
    assert change_requires_user_confirm(family)
    assert change_requires_user_confirm(factor)
    assert change_requires_user_confirm(proxy)
    assert change_requires_user_confirm(binding)
    assert change_requires_user_confirm(source)
    assert "data_lineage" in {kind.value for kind in ConfirmKind}


def test_changing_family_or_primary_factor_waits_for_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "1")

    class FamilyBuilder(FailedMethodsParamBuilder):
        def next_change(self, accepted):
            del accepted
            return ProposedChange("strategy_family", "mean_reversion", "low_volatility")

    class FactorBuilder(FailedMethodsParamBuilder):
        def next_change(self, accepted):
            del accepted
            return ProposedChange("primary_factor", None, "value")

    store = SQLiteStore(tmp_path / "family.db")
    store.create(running_research())
    waiting = ResearchLoop(
        store,
        FamilyBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert waiting.status is ResearchStatus.AWAITING_CONFIRM
    assert waiting.pending_confirm is not None
    assert waiting.pending_confirm.kind is ConfirmKind.ECONOMIC
    assert waiting.pending_confirm.patch[0][0] == "strategy_family"

    store_factor = SQLiteStore(tmp_path / "factor.db")
    store_factor.create(running_research())
    factor_wait = ResearchLoop(
        store_factor,
        FactorBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert factor_wait.status is ResearchStatus.AWAITING_CONFIRM
    assert factor_wait.pending_confirm is not None
    assert factor_wait.pending_confirm.kind is ConfirmKind.ECONOMIC
    assert factor_wait.pending_confirm.patch[0][0] == "primary_factor"


def test_data_lineage_change_waits_without_economic_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "1")

    class SourceBuilder(FailedMethodsParamBuilder):
        def next_change(self, accepted):
            return ProposedChange("data_source_id", "yahoo_daily", "local_file")

    store = SQLiteStore(tmp_path / "lineage.db")
    store.create(running_research())
    waiting = ResearchLoop(
        store,
        SourceBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert waiting.status is ResearchStatus.AWAITING_CONFIRM
    assert waiting.pending_confirm is not None
    assert waiting.pending_confirm.kind.value == "data_lineage"
    assert waiting.pending_confirm.patch == (("data_source_id", "local_file"),)


def test_reviewer_judges_strategy_family_not_model_family() -> None:
    base = _draft(True)
    other = replace(base, attempt=replace(base.attempt, spec=replace(_spec(), strategy_family="low_volatility")))
    assert default_v1_pass(other) is False
    assert DeterministicReviewer().run(other).passed is False

    legacy = replace(
        base,
        attempt=replace(
            base.attempt,
            spec=replace(
                _spec(family="momentum"),
                strategy_family="legacy_mean_reversion",
                family_method="legacy_zscore_daily",
            ),
        ),
    )
    assert default_v1_pass(legacy) is True


def test_family_ids_are_a_closed_list_and_display_names_are_not_stored() -> None:
    from engine.research.families import FAMILY_IDS, family_display_name

    assert FAMILY_IDS == (
        "low_volatility",
        "stock_bond_rebalance",
        "mean_reversion",
        "fundamental_factor",
        "all_weather",
        "legacy_mean_reversion",
    )
    assert family_display_name("mean_reversion", "zh") == "均值回归"
    assert family_display_name("mean_reversion", "en") == "mean_reversion"
    assert family_display_name("legacy_mean_reversion", "zh") == "均值回归（旧版）"
    assert family_display_name("legacy_mean_reversion", "en") == "legacy_mean_reversion"
    with pytest.raises(ValueError):
        replace(_spec(), strategy_family="momentum")


class _SocketPort:
    def __init__(self) -> None:
        self.loads = 0
        self.windows: list[tuple[date, date]] = []

    def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).close()
        self.loads += 1
        self.windows.append((start, end))
        index = pd.bdate_range(PIN_START, periods=40)
        if symbols == ("SPX",):
            return pd.DataFrame({"SPX": [100.0 + i for i in range(40)]}, index=index)
        return pd.DataFrame({symbol: [10.0 + i for i in range(40)] for symbol in symbols}, index=index)


class _SocketMaterials:
    def __init__(self) -> None:
        self.fetches = 0

    def fetch(self, query: str) -> tuple[object, ...]:
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).close()
        self.fetches += 1
        return ()


def _running_pinned(store: SQLiteStore, research_id: str = "a1-freeze") -> None:
    research = new_research(research_id, NOW)
    store.create(research)
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA", "BBB"))
    methods = (
        MethodRef("overfit.walk", "walk-v1"),
        MethodRef("stability.oos", "stability-v1"),
        MethodRef("crowding.load", "crowding-v1"),
        MethodRef("cost.turnover", "cost-v1"),
    )
    locked = replace(
        research,
        brief=replace(
            research.brief,
            thesis=Slot("cross sectional mean reversion", True),
            universe=Slot(universe, True),
            max_effective_hours=Slot(48.0, True),
            round1_methods=Slot(methods, True),
            coverage_floor=Slot(CoverageFloor(2, 5, 0.2), True),
        ),
        data_window_start=PIN_START,
        data_window_end=PIN_END,
        data_source_id="yahoo_daily",
    )
    store.save(locked, locked.updated_at)
    running = transition(locked, ResearchEvent.CONFIRM_RUN, NOW)
    store.save(running, running.updated_at)


class _DummySocket:
    def close(self) -> None:
        return None


def _guard(opened: list[int]):
    def guard(*args: object, **kwargs: object) -> _DummySocket:
        opened.append(1)
        return _DummySocket()

    return guard


def test_same_version_second_round_does_not_open_sockets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[int] = []
    monkeypatch.setattr(socket, "socket", _guard(opened))
    store = SQLiteStore(tmp_path / "freeze.db")
    _running_pinned(store)
    paths = EnginePaths.for_colocated_root(tmp_path)
    port = _SocketPort()
    materials = _SocketMaterials()
    builder = DefaultRoundBuilder(
        material_ports=(materials,),  # type: ignore[arg-type]
        data_port=port,
        start=PROCESS_START,
        end=PROCESS_END,
        snapshot_root=paths.data.snapshots_dir,
    )
    research = store.load("a1-freeze")
    before = len(opened)
    builder.build(research, 1)
    assert len(opened) > before
    assert port.windows
    assert set(port.windows) == {(PIN_START, PIN_END)}

    again = len(opened)
    builder.build(research, 1)
    assert len(opened) == again
    assert materials.fetches == 1

    fresh_port = _SocketPort()
    fresh = DefaultRoundBuilder(
        material_ports=(_SocketMaterials(),),  # type: ignore[arg-type]
        data_port=fresh_port,
        start=PROCESS_START,
        end=PROCESS_END,
        snapshot_root=paths.data.snapshots_dir,
    )
    fresh.build(research, 1)
    assert len(opened) == again
    assert fresh_port.loads == 0


def test_retry_and_version_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[int] = []
    monkeypatch.setattr(socket, "socket", _guard(opened))
    store = SQLiteStore(tmp_path / "boundary.db")
    _running_pinned(store, "a1-boundary")
    paths = EnginePaths.for_colocated_root(tmp_path)
    port = _SocketPort()
    builder = DefaultRoundBuilder(
        material_ports=(_SocketMaterials(),),  # type: ignore[arg-type]
        data_port=port,
        start=PROCESS_START,
        end=PROCESS_END,
        snapshot_root=paths.data.snapshots_dir,
    )
    research = store.load("a1-boundary")
    draft = builder.build(research, 1)
    after_first = len(opened)
    from engine.research.models import ReviewReport

    builder.retry(draft, ReviewReport(False, ()))
    assert len(opened) == after_first

    second_version = replace(
        research,
        current_version_number=2,
        versions=research.versions
        + (
            replace(
                research.versions[0],
                version_id="a1-boundary-v2",
                number=2,
                rounds=(),
            ),
        ),
    )
    builder.build(second_version, 1)
    assert len(opened) > after_first


def test_build_loop_does_not_use_process_start_or_global_router(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FrozenDate(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            return datetime(1999, 1, 1, tzinfo=tz)

    monkeypatch.setattr("engine.main.datetime", FrozenDate)
    paths = EnginePaths.for_colocated_root(tmp_path)
    store = SQLiteStore(paths.data.database_file)
    loop = build_loop(store, paths)
    assert loop.builder.start != date(1999, 1, 1)  # type: ignore[attr-defined]
    assert loop.builder.end != date(1999, 1, 1)  # type: ignore[attr-defined]
    assert not isinstance(loop.builder.data_port, RoutingDataAdapter)  # type: ignore[attr-defined]


def test_shrink_uses_symbol_rule_without_fixed_router(monkeypatch: pytest.MonkeyPatch) -> None:
    set_pool_data_loader(None)
    constructed: list[str] = []

    class Router:
        def __init__(self, *args: object, **kwargs: object) -> None:
            constructed.append("router")

        def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
            return pd.DataFrame(
                {symbols[0]: [1.0, 2.0]},
                index=pd.bdate_range("2020-01-02", periods=2),
            )

    class Yahoo:
        def __init__(self) -> None:
            constructed.append("yahoo")

        def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
            return pd.DataFrame(
                {symbols[0]: [1.0, 2.0]},
                index=pd.bdate_range("2020-01-02", periods=2),
            )

    class Ak:
        def __init__(self) -> None:
            constructed.append("akshare")

        def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
            return pd.DataFrame(
                {symbols[0]: [1.0, 2.0]},
                index=pd.bdate_range("2020-01-02", periods=2),
            )

    monkeypatch.setattr("engine.research.gather.RoutingDataAdapter", Router)
    monkeypatch.setattr("engine.research.gather.YahooDataAdapter", Yahoo)
    monkeypatch.setattr("engine.research.gather.AkShareDataAdapter", Ak)
    kept = symbols_with_daily_data(("AAPL",), date(2020, 1, 2), date(2020, 1, 8))
    assert kept == ("AAPL",)
    assert "router" not in constructed
    assert "akshare" not in constructed


def test_unbound_source_is_not_sent_to_yahoo() -> None:
    research = replace(new_research("r-unbound", NOW), data_source_id="pending")
    with pytest.raises(UserFacingError) as exc:
        data_port_for_research(research)
    assert exc.value.code == "DATA_SOURCE_UNBOUND"
    text = exc.value.message.lower()
    assert "http" not in text
    assert "yahoo" not in text
    assert "akshare" not in text


def test_old_spec_reverify_is_bit_identical(tmp_path: Path) -> None:
    panel = snapshot()
    classic = StrategySpec(
        id="mean-reversion-pack",
        thesis_locked="one-day reversal",
        universe=Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA", "BBB")),
        frequency="1d",
        side="long_only",
        method_set=(),
        model_family="mean_reversion",
        lookback_days=2,
        entry_z=0.5,
    )
    baseline = run_daily_backtest(MeanReversionStrategy(classic), panel).tolist()
    research = completed_research()
    store = SQLiteStore(tmp_path / "old.db")
    store.create(research)
    raw = store.connection.execute(
        "SELECT state_json FROM researches WHERE research_id=?",
        (research.research_id,),
    ).fetchone()[0]
    import json

    payload = json.loads(raw)
    spec_payload = payload["versions"][0]["rounds"][0]["accepted_attempt"]["spec"]
    for key in ("strategy_family", "family_method", "family_params", "primary_factor"):
        spec_payload.pop(key, None)
    with store.connection:
        store.connection.execute(
            "UPDATE researches SET state_json=? WHERE research_id=?",
            (json.dumps(payload), research.research_id),
        )
    loaded = store.load(research.research_id)
    spec = loaded.versions[0].rounds[0].accepted_attempt.spec
    assert spec.strategy_family == "mean_reversion"
    assert spec.family_method == "legacy_zscore_daily"
    assert spec.family_params == ()
    assert spec.primary_factor is None
    assert run_daily_backtest(MeanReversionStrategy(spec), panel).tolist() == baseline
    assert "均值回归" not in json.dumps(spec_payload)

    frame = panel.prices.copy()
    assert panel.benchmark_prices is not None
    frame["__benchmark__"] = panel.benchmark_prices
    snapshot_path = tmp_path / "frozen.csv"
    frame.to_csv(snapshot_path, index_label="date")
    attempt = loaded.versions[0].rounds[0].accepted_attempt
    updated = replace(
        loaded,
        versions=(
            replace(
                loaded.versions[0],
                rounds=(
                    replace(
                        loaded.versions[0].rounds[0],
                        accepted_attempt=replace(attempt, data_snapshot_path=snapshot_path),
                    ),
                ),
            ),
        ),
    )
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path / "svc"))
    service.store.save(updated, loaded.updated_at)
    service.handle(
        {
            "type": "reverify",
            "research_id": updated.research_id,
            "round_id": updated.versions[0].rounds[0].round_id,
            "method_id": "scorecard.market",
        }
    )
    report = service.store.load(updated.research_id).reverifications[-1].report
    results = report["results"] if isinstance(report, dict) else report.results
    revisions = {
        item["verifier_id"] if isinstance(item, dict) else item.verifier_id: (
            item["revision"] if isinstance(item, dict) else item.revision
        )
        for item in results
    }
    assert revisions["scorecard.market"] == "scorecard-v1"
    assert revisions["pit.consistency"] == "pit-v1"
