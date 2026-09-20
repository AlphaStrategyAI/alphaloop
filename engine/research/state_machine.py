from dataclasses import replace
from datetime import datetime

from engine.research.models import (
    ConfirmKind,
    ConfirmRequest,
    CoverageFloor,
    Research,
    ResearchBrief,
    ResearchEvent,
    ResearchStatus,
    Slot,
    Version,
    assert_preconfirm_evidence,
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
    if opened_by != "modified_settings_confirm":
        changes = research.pending_confirm.patch if research.pending_confirm else ()
        for field_name, value in changes:
            if field_name == "coverage_floor" and isinstance(value, dict):
                value = CoverageFloor(**value)
            if hasattr(brief, field_name):
                brief = replace(brief, **{field_name: Slot(value, True)})  # type: ignore[arg-type]
    else:
        changes = ()
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
    store: object | None = None,
) -> Research:
    """Transition research to a new state based on event.
    
    Args:
        research: Current research state
        event: Event triggering the transition
        now: Current timestamp
        request: ConfirmRequest for REQUEST_CONFIRM event
        store: Evidence store for CONFIRM_APPROVE validation (B4 iron rule)
    
    Raises:
        InvalidTransition: If the event is not valid for current status
        InvalidEvidenceRefError: If CONFIRM_APPROVE fails evidence validation
    """
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
        if research.pending_confirm is None:
            raise InvalidTransition("CONFIRM_APPROVE requires pending_confirm")
        # B4 iron rule: ECONOMIC confirms require evidence validation
        # COVERAGE confirms are automated (data availability) and don't require evidence
        if research.pending_confirm.kind is ConfirmKind.ECONOMIC:
            if store is None:
                raise InvalidTransition(
                    "CONFIRM_APPROVE requires store for evidence validation (B4 iron rule)"
                )
            assert_preconfirm_evidence(research.pending_confirm, store)
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
        status
        in {
            ResearchStatus.AWAITING_CONFIRM,
            ResearchStatus.PAUSED,
            ResearchStatus.COMPLETED,
            ResearchStatus.ENDED,
        }
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
