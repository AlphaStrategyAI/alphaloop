"""B4 economic confirm E2E on real SQLite (not Done #1 evidence).

Includes -0.35 max_drawdown_floor via resolve_confirm + EvidenceRef lookup.
"""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.clock import TimeBudget
from engine.research.loop import ResearchLoop
from engine.research.models import EvidenceKind, ResearchStatus
from engine.research.runtime import EnginePaths
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from tests.test_loop_runtime import (
    NOW,
    EconomicDrawdown35Builder,
    PassReviewer,
    running_research,
)


def test_b4_resolve_confirm_sqlite_lookup_minus_035(tmp_path: Path) -> None:
    """NOT Done #1: -0.35 only via economic confirm on SQLite store."""
    db = tmp_path / "b4.db"
    store = SQLiteStore(db)
    paths = EnginePaths.for_colocated_root(tmp_path)
    service = ResearchCommandService(store, paths)
    store.create(running_research())
    waiting = ResearchLoop(
        store,
        EconomicDrawdown35Builder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert waiting.status is ResearchStatus.AWAITING_CONFIRM
    attempt_id = waiting.versions[0].rounds[0].accepted_attempt.attempt_id
    assert store.get_attempt(attempt_id) is not None
    trials_before = waiting.versions[0].rounds[0].trial_counters.candidates_evaluated

    evidence_time = NOW.replace(hour=10).isoformat()
    confirm_time = NOW.replace(hour=11)
    pending = waiting.pending_confirm
    assert pending is not None
    store.save(
        replace(
            waiting,
            pending_confirm=replace(pending, created_at=confirm_time),
        ),
        waiting.updated_at,
    )

    payload = service.handle(
        {
            "type": "resolve_confirm",
            "research_id": "r-loop",
            "decision": "approve_new_version",
            "who_pays": "流动性提供者",
            "why_change": [
                {
                    "record_id": attempt_id,
                    "recorded_at": evidence_time,
                    "kind": EvidenceKind.ATTEMPT.value,
                    "summary": "scorecard.market failed at default floor",
                }
            ],
        }
    )
    assert payload["status"] == "running"
    approved = store.load("r-loop")
    assert len(approved.versions) == 2
    v2 = approved.versions[1]
    assert v2.opened_by == "economic_confirm"
    assert ("max_drawdown_floor", -0.35) in v2.confirmed_changes
    assert approved.versions[0].rounds[0].trial_counters.candidates_evaluated == trials_before

    view = service.view_for("#/research/r-loop")
    assert view["kind"] == "running"
    assert view["version"] == 2
