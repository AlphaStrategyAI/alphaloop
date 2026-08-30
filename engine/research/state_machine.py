from dataclasses import replace
from datetime import datetime

from engine.research.models import (
    ConfirmRequest,
    Research,
    ResearchBrief,
    ResearchEvent,
    ResearchStatus,
    Slot,
    Version,
)


class InvalidTransition(ValueError):
    """Raised when an event is not valid for the current research status."""


def all_slots_locked(brief: ResearchBrief) -> bool:
    slots = (
        brief.thesis,
        brief.universe,
        brief.max_effective_hours,
        brief.round1_methods,
        brief.coverage_floor,
    )
    return all(slot.locked and slot.value is not None for slot in slots)


def _open_version(research: Research, now: datetime, opened_by: str) -> Research:
    brief = research.brief
    changes = research.pending_confirm.patch if research.pending_confirm else ()
    for field_name, value in changes:
        if hasattr(brief, field_name):
            brief = replace(brief, **{field_name: Slot(value, True)})  # type: ignore[arg-type]
    number = len(research.versions) + 1
    version = Version(
        version_id=f"{research.research_id}-v{number}",
        number=number,
        brief_snapshot=brief,
        rounds=(),
        opened_at=now,
        opened_by=opened_by,
        confirmed_changes=changes,
    )
    return replace(
        research,
        status=ResearchStatus.RUNNING,
        brief=brief,
        versions=research.versions + (version,),
        current_version_number=number,
        pending_confirm=None,
        export_eligible=False,
        updated_at=now,
    )


def transition(
    research: Research,
    event: ResearchEvent,
    now: datetime,
    request: ConfirmRequest | None = None,
) -> Research:
    status = research.status
    if status is ResearchStatus.DRAFT and event is ResearchEvent.EDIT_DRAFT:
        return replace(research, updated_at=now)
    if status is ResearchStatus.DRAFT and event is ResearchEvent.CONFIRM_RUN:
        if not all_slots_locked(research.brief):
            raise InvalidTransition("draft cannot confirm_run until all five slots are locked")
        return _open_version(research, now, "confirm_run")
    if status is ResearchStatus.RUNNING and event is ResearchEvent.AUTO_CONTINUE:
        return replace(research, updated_at=now)
    if status is ResearchStatus.RUNNING and event is ResearchEvent.REQUEST_CONFIRM:
        if request is None:
            raise InvalidTransition("request_confirm requires ConfirmRequest")
        return replace(
            research,
            status=ResearchStatus.AWAITING_CONFIRM,
            pending_confirm=request,
            updated_at=now,
        )
    if status is ResearchStatus.RUNNING and event is ResearchEvent.PAUSE:
        return replace(research, status=ResearchStatus.PAUSED, updated_at=now)
    if status is ResearchStatus.RUNNING and event is ResearchEvent.COMPLETE:
        return replace(
            research,
            status=ResearchStatus.COMPLETED,
            export_eligible=True,
            updated_at=now,
        )
    if status is ResearchStatus.RUNNING and event is ResearchEvent.BUDGET_EXHAUSTED:
        return replace(research, status=ResearchStatus.ENDED, updated_at=now)
    if status is ResearchStatus.AWAITING_CONFIRM and event is ResearchEvent.CONFIRM_APPROVE:
        return _open_version(research, now, "economic_confirm")
    if status is ResearchStatus.AWAITING_CONFIRM and event is ResearchEvent.CONFIRM_REJECT:
        return replace(
            research,
            status=ResearchStatus.RUNNING,
            pending_confirm=None,
            consecutive_review_failures=0,
            updated_at=now,
        )
    if status is ResearchStatus.AWAITING_CONFIRM and event is ResearchEvent.CONFIRM_PAUSE:
        return replace(
            research,
            status=ResearchStatus.PAUSED,
            pending_confirm=None,
            updated_at=now,
        )
    if status is ResearchStatus.PAUSED and event is ResearchEvent.RESUME:
        return replace(research, status=ResearchStatus.RUNNING, updated_at=now)
    if status is ResearchStatus.COMPLETED and event is ResearchEvent.REVERIFY_PASS:
        return replace(research, updated_at=now)
    if status is ResearchStatus.COMPLETED and event is ResearchEvent.REVERIFY_FAIL:
        return replace(research, export_eligible=False, updated_at=now)
    if (
        status in {ResearchStatus.PAUSED, ResearchStatus.COMPLETED, ResearchStatus.ENDED}
        and event is ResearchEvent.MODIFY_CONFIRM
    ):
        return _open_version(research, now, "modified_settings_confirm")
    if status is ResearchStatus.ENDED and event is ResearchEvent.EXTEND_CONFIRM:
        return _open_version(research, now, "extended_budget_confirm")
    if event is ResearchEvent.WAIT and status in {
        ResearchStatus.AWAITING_CONFIRM,
        ResearchStatus.PAUSED,
        ResearchStatus.ENDED,
    }:
        return research
    raise InvalidTransition(f"{status.value} cannot handle {event.value}")
