"""Economic confirm: engine fills why_change from pre-confirm attempt (real loop + SQLite)."""

from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.clock import TimeBudget
from engine.research.loop import ResearchLoop
from engine.research.models import EvidenceKind, ResearchStatus
from engine.research.models import assert_preconfirm_evidence
from engine.research.runtime import RuntimePaths
from engine.research.store import SQLiteStore
from tests.test_loop_runtime import NOW, EconomicBuilder, PassReviewer, running_research


def test_real_loop_populates_why_change_and_approve_opens_v2(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "econ-evidence.db")
    paths = RuntimePaths(tmp_path, tmp_path / "lock", tmp_path / "owner.json")
    service = ResearchCommandService(store, paths)
    store.create(running_research())

    waiting = ResearchLoop(
        store,
        EconomicBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")

    assert waiting.status is ResearchStatus.AWAITING_CONFIRM
    pending = waiting.pending_confirm
    assert pending is not None
    assert pending.kind.value == "economic"
    assert len(pending.why_change) >= 1
    attempt_id = waiting.versions[0].rounds[0].accepted_attempt.attempt_id
    assert pending.why_change[0].record_id == attempt_id
    assert pending.why_change[0].kind is EvidenceKind.ATTEMPT
    assert pending.created_at is not None
    assert all(ref.recorded_at < pending.created_at for ref in pending.why_change)

    assert_preconfirm_evidence(pending, store, "r-loop")

    view = service.view_for("#/research/r-loop")
    assert view["kind"] == "awaiting_confirm"
    why = view["whyChange"]
    assert isinstance(why, list) and len(why) >= 1
    assert why[0]["recordId"] == attempt_id

    payload = service.handle(
        {
            "type": "resolve_confirm",
            "research_id": "r-loop",
            "decision": "approve_new_version",
            "who_pays": "测试",
        }
    )
    assert payload["status"] == "running"

    approved = store.load("r-loop")
    assert len(approved.versions) == 2
    assert approved.versions[1].opened_by == "economic_confirm"
    assert approved.pending_confirm is None

    running_view = service.view_for("#/research/r-loop")
    assert running_view["kind"] == "running"
    assert running_view["version"] == 2
