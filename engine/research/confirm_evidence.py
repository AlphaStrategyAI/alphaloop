from __future__ import annotations

from datetime import datetime, timedelta

from engine.research.models import Attempt, EvidenceKind, EvidenceRef
from engine.research.methods import format_verifier_display


def evidence_refs_from_failed_attempt(
    attempt: Attempt,
    *,
    recorded_at: datetime,
) -> tuple[EvidenceRef, ...]:
    """B4: cite the pre-confirm accepted attempt and its failed gates only."""
    verification = attempt.verification
    if verification is None:
        return (
            EvidenceRef(
                record_id=attempt.attempt_id,
                recorded_at=recorded_at,
                kind=EvidenceKind.ATTEMPT,
                summary="验证记录不可用",
            ),
        )
    failed = [item for item in verification.results if not item.passed]
    if not failed:
        return (
            EvidenceRef(
                record_id=attempt.attempt_id,
                recorded_at=recorded_at,
                kind=EvidenceKind.ATTEMPT,
                summary="冻结验证未全部通过",
            ),
        )
    labels = "、".join(format_verifier_display(item.verifier_id) for item in failed)
    return (
        EvidenceRef(
            record_id=attempt.attempt_id,
            recorded_at=recorded_at,
            kind=EvidenceKind.ATTEMPT,
            summary=f"未通过：{labels}",
        ),
    )


def confirm_created_at_after_evidence(
    evidence: tuple[EvidenceRef, ...],
    now: datetime,
) -> datetime:
    if not evidence:
        return now
    latest = max(ref.recorded_at for ref in evidence)
    if latest >= now:
        return latest + timedelta(seconds=1)
    return now
