"""§2.3 network acceptance: real MaterialPort + DataPort → COMPLETED.

Undated local notes are browsed, not cited. PIT passes with evidence_used=0.
Other gates are reported as they come back; this test does not require them green.
"""

import os
from datetime import UTC, date, datetime

import pytest

from engine.research.clock import TimeBudget
from engine.research.gather import LocalMaterialAdapter, RoutingDataAdapter, YahooDataAdapter, AkShareDataAdapter
from engine.research.loop import DefaultRoundBuilder, ResearchLoop
from engine.research.models import ResearchStatus, Slot, Universe, AssetClass, Market, MethodRef, CoverageFloor, new_research
from engine.research.runtime import EnginePaths
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.research.models import ResearchEvent
from engine.review.deterministic import DeterministicReviewer

pytestmark = pytest.mark.network

# SPY daily window frozen for acceptance (default max_drawdown_floor -0.25; no threshold override).
_SCORECARD_WINDOW_START = date(2000, 1, 4)
_SCORECARD_WINDOW_END = date(2010, 12, 31)


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
    paths = EnginePaths.for_colocated_root(tmp_path)
    builder = DefaultRoundBuilder(
        material_ports=(LocalMaterialAdapter(material_dir, lambda: now),),
        data_port=RoutingDataAdapter(YahooDataAdapter(), AkShareDataAdapter()),
        start=_SCORECARD_WINDOW_START,
        end=_SCORECARD_WINDOW_END,
        snapshot_root=paths.data.snapshots_dir,
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
    store.save(running, running.updated_at)
    current = running
    for _ in range(12):
        if current.status is ResearchStatus.COMPLETED:
            break
        current = loop.run_once(current.research_id)
    assert current.status is ResearchStatus.COMPLETED
    assert len(current.versions[-1].rounds) >= 1
    attempt = current.versions[-1].rounds[-1].accepted_attempt
    pit = next(
        item
        for item in attempt.verification.results
        if item.verifier_id == "pit.consistency"
    )
    assert pit.verifier_id == "pit.consistency"
    assert pit.revision == "pit-v2"
    assert pit.passed is True
    assert pit.evidence_used == 0
    assert pit.note == "未引用外部资料"
    assert any(str(item).startswith("local:") for item in pit.undated_excluded)
    assert pit.scope == "只查资料发布日 ≤ 回测截止日，不覆盖标的池/复权/财务修订"

    from engine.export import build_research_record_pack, strategy_pack_eligibility
    from engine.research.desktop_view import rounds_for_desktop

    eligibility = strategy_pack_eligibility(current)
    assert "pit_executed_and_passed" not in eligibility.failed_checks
    method_set = tuple(m for m in attempt.spec.method_set if m.method_id != "pit.consistency")
    methods_passed = attempt.verification.passed_for(method_set)
    if not methods_passed:
        assert "all_current_methods_passed" in eligibility.failed_checks
        scorecard = next(
            r for r in attempt.verification.results if r.verifier_id == "scorecard.market"
        )
        if not scorecard.passed:
            assert scorecard.verifier_id == "scorecard.market"

    desktop_rounds = rounds_for_desktop(current, current.current_version_number or 1)
    assert desktop_rounds[0]["verificationPassed"] is methods_passed
    assert desktop_rounds[0]["pitPassed"] is True

    record_path = build_research_record_pack(current, tmp_path / "accept-record.zip")
    assert record_path.exists()
