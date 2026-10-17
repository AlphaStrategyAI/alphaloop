from datetime import UTC, datetime

from engine.research.confirm_evidence import (
    confirm_created_at_after_evidence,
    evidence_refs_from_failed_attempt,
)
from engine.research.models import EvidenceKind
from tests.test_loop_runtime import NOW, report


def test_evidence_refs_from_failed_attempt_lists_failed_gate_labels() -> None:
    from engine.research.models import Attempt, ChangeClass
    from tests.test_loop_runtime import simulation, strategy

    attempt = Attempt(
        attempt_id="a-ev-1",
        number=1,
        change_class=ChangeClass.PARAM,
        spec=strategy(1),
        simulation=simulation(),
        verification=report(False),
        review=None,
    )
    recorded = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)
    refs = evidence_refs_from_failed_attempt(attempt, recorded_at=recorded)
    assert len(refs) == 1
    ref = refs[0]
    assert ref.record_id == "a-ev-1"
    assert ref.kind is EvidenceKind.ATTEMPT
    assert ref.recorded_at == recorded
    assert "未通过" in (ref.summary or "")
    assert "scorecard" in (ref.summary or "").lower() or "市场" in (ref.summary or "")


def test_confirm_created_at_after_evidence_is_strictly_after() -> None:
    recorded = NOW.replace(hour=10)
    from engine.research.models import EvidenceRef

    refs = (
        EvidenceRef(
            record_id="a-1",
            recorded_at=recorded,
            kind=EvidenceKind.ATTEMPT,
            summary="x",
        ),
    )
    created_after = confirm_created_at_after_evidence(refs, NOW.replace(hour=11))
    assert created_after == NOW.replace(hour=11)
    created_same = confirm_created_at_after_evidence(refs, recorded)
    assert created_same > recorded
