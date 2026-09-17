from datetime import UTC, datetime
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.methods import (
    create_method,
    deposit_method,
    list_method_usage,
    record_method_usage,
    revise_method,
)
from engine.research.runtime import RuntimePaths
from engine.research.models import (
    MethodRef,
    MethodSource,
    new_research,
)
from engine.research.store import SQLiteStore
from engine.metrics import SimulationReport
from engine.research.models import AssetClass, Market, Universe
from engine.strategy import StrategySpec
from engine.verifiers import run_verifiers

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def test_revise_creates_a_new_definition_and_keeps_the_old_row(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "m.db")
    first = create_method(
        store, "custom.gap", "缺口", "v1 body", "body-v1", MethodSource.PRESET, NOW
    )
    second = revise_method(store, "custom.gap", "缺口", "v2 body", "body-v2", NOW)
    rows = store.list_method_definitions()
    assert len(rows) == 2
    assert first.revision_hash != second.revision_hash
    assert second.supersedes == first.revision_hash
    assert {row.revision_hash for row in rows} == {first.revision_hash, second.revision_hash}


def test_deposit_marks_source_and_survives_research_delete(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "m.db")
    research = new_research("r-dep", NOW)
    store.create(research)
    deposited = deposit_method(
        store, "r-dep", "custom.gap", "缺口", "from research", "body", NOW
    )
    record_method_usage(
        store,
        "r-dep",
        1,
        (MethodRef(deposited.method_id, deposited.revision_hash),),
    )
    store.delete("r-dep")
    assert store.list_method_definitions()[0].source is MethodSource.DEPOSITED
    assert store.list_method_definitions()[0].deposited_from_research_id == "r-dep"
    assert list_method_usage(store, "custom.gap")[0].research_id == "r-dep"


def test_library_create_method_is_deposited_not_preset(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "m.db")
    service = ResearchCommandService(
        store,
        RuntimePaths(tmp_path, tmp_path / "engine.lock", tmp_path / "owner.json"),
    )
    service.handle(
        {
            "type": "create_method",
            "method_id": "user.gap",
            "name": "缺口",
            "description": "user authored",
            "body": "body",
        }
    )
    created = store.latest_method_definition("user.gap")
    assert created is not None
    assert created.source is MethodSource.DEPOSITED
    assert created.deposited_from_research_id is None
    presets = {
        item.method_id
        for item in store.list_method_definitions()
        if item.source is MethodSource.PRESET
    }
    assert "user.gap" not in presets
    assert presets == {
        "scorecard.market",
        "overfit.walk",
        "stability.oos",
        "crowding.load",
        "cost.turnover",
    }


def test_selected_method_set_must_all_pass_and_does_not_inherit_old_passes() -> None:
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA",))
    report = SimulationReport(
        r_total=0.2,
        r_ann=0.12,
        sharpe=0.9,
        vol_ann=0.13,
        max_drawdown=-0.2,
        benchmark_id="SPX",
        r_bench_ann=0.08,
        excess_ann=0.04,
        tracking_error=0.06,
        information_ratio=2 / 3,
        sharpe_oos=0.7,
        sharpe_is=1.0,
        oos_segment_returns=(0.02, 0.01, -0.005),
        top_20_crowding_sharpe_impact=0.01,
        annual_turnover=1.0,
        observations=756,
        covered_assets=1,
        missing_pct=0.0,
    )
    four = (
        MethodRef("overfit.walk", "walk-v1"),
        MethodRef("stability.oos", "stability-v1"),
        MethodRef("crowding.load", "crowding-v1"),
        MethodRef("cost.turnover", "cost-v1"),
    )
    spec = StrategySpec(
        id="s-m",
        thesis_locked="reversal",
        universe=universe,
        frequency="1d",
        side="long_only",
        method_set=four,
        model_family="mean_reversion",
        lookback_days=20,
        entry_z=1.0,
        max_drawdown_floor=-0.25,
    )
    assert run_verifiers(report, spec).passed
    extra = StrategySpec(
        id="s-m",
        thesis_locked="reversal",
        universe=universe,
        frequency="1d",
        side="long_only",
        method_set=four + (MethodRef("custom.gap", "gap-v1"),),
        model_family="mean_reversion",
        lookback_days=20,
        entry_z=1.0,
        max_drawdown_floor=-0.25,
    )
    result = run_verifiers(report, extra)
    assert result.passed is False
    assert any(item.verifier_id == "custom.gap" and not item.passed for item in result.results)
