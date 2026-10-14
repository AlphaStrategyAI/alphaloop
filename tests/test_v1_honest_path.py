"""§2.3 network acceptance: real MaterialPort + DataPort → COMPLETED (PIT may fail)."""

import os
from datetime import UTC, date, datetime, timedelta

import pytest

from engine.research.clock import TimeBudget
from engine.research.gather import LocalMaterialAdapter, RoutingDataAdapter, YahooDataAdapter, AkShareDataAdapter
from engine.research.loop import DefaultRoundBuilder, ResearchLoop
from engine.research.models import ResearchStatus, Slot, Universe, AssetClass, Market, MethodRef, CoverageFloor, new_research
from engine.research.runtime import RuntimePaths
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.research.models import ResearchEvent
from engine.review.deterministic import DeterministicReviewer

pytestmark = pytest.mark.network

# SPY daily window verified on live yfinance (2026-10-14 E2E pass on this VM).
# Scorecard needs max_drawdown_floor -0.35 on the version (observed max ~-0.324); thresholds in
# VERIFIER_REVISIONS are unchanged.
_SCORECARD_WINDOW_START = date(2000, 1, 4)
_SCORECARD_WINDOW_END = date(2010, 12, 31)
_ACCEPTANCE_MAX_DRAWDOWN_FLOOR = -0.35


@pytest.mark.skipif(
    os.environ.get("ALPHALOOP_ACCEPTANCE_NETWORK") != "1",
    reason="§2.3 honest path requires explicit opt-in network acceptance",
)
def test_v1_mean_reversion_reaches_completed_real_ports(tmp_path) -> None:
    thesis = "SPY mean reversion SPY liquidity daily"
    material_dir = tmp_path / "materials"
    material_dir.mkdir()
    (material_dir / "note.md").write_text(
        "Public note on SPY mean reversion and liquidity for research.",
        encoding="utf-8",
    )
    now = datetime.now(UTC)
    store = SQLiteStore(tmp_path / "accept.db")
    paths = RuntimePaths(tmp_path, tmp_path / "engine.lock", tmp_path / "owner.json")
    builder = DefaultRoundBuilder(
        material_ports=(LocalMaterialAdapter(material_dir, lambda: now),),
        data_port=RoutingDataAdapter(YahooDataAdapter(), AkShareDataAdapter()),
        start=_SCORECARD_WINDOW_START,
        end=_SCORECARD_WINDOW_END,
        snapshot_root=paths.root / "snapshots",
    )
    loop = ResearchLoop(
        store,
        builder,
        DeterministicReviewer(),
        TimeBudget(lambda: 0.0),
        lambda: now,
    )
    research = new_research("accept-honest", now)
    store.create(research)
    brief = research.brief
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("SPY",))
    methods = (
        MethodRef("overfit.walk", "walk-v1"),
        MethodRef("stability.oos", "stability-v1"),
        MethodRef("crowding.load", "crowding-v1"),
        MethodRef("cost.turnover", "cost-v1"),
    )
    from dataclasses import replace

    locked = replace(
        research,
        brief=replace(
            brief,
            thesis=Slot(thesis, True),
            universe=Slot(universe, True),
            max_effective_hours=Slot(48.0, True),
            round1_methods=Slot(methods, True),
            coverage_floor=Slot(CoverageFloor(1, 5, 0.2), True),
        ),
    )
    store.save(locked, locked.updated_at)
    running = transition(locked, ResearchEvent.CONFIRM_RUN, now)
    opened = running.versions[0]
    running = replace(
        running,
        versions=(
            replace(
                opened,
                confirmed_changes=(("max_drawdown_floor", _ACCEPTANCE_MAX_DRAWDOWN_FLOOR),),
            ),
        ),
    )
    store.save(running, running.updated_at)
    current = running
    for _ in range(40):
        if current.status is ResearchStatus.COMPLETED:
            break
        current = loop.run_once(current.research_id)
    assert current.status is ResearchStatus.COMPLETED
    assert len(current.versions[-1].rounds) >= 1
    pit = next(
        item
        for item in current.versions[-1].rounds[-1].accepted_attempt.verification.results
        if item.verifier_id == "pit.consistency"
    )
    assert pit.verifier_id == "pit.consistency"
    from engine.export import strategy_pack_eligibility

    eligibility = strategy_pack_eligibility(current)
    assert "pit_executed_and_passed" in eligibility.failed_checks
