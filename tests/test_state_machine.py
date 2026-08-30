from dataclasses import replace
from datetime import UTC, datetime

import pytest

from engine.research.models import (
    AssetClass,
    ConfirmKind,
    ConfirmRequest,
    CoverageFloor,
    Market,
    MethodRef,
    ResearchBrief,
    ResearchEvent,
    ResearchStatus,
    Slot,
    Universe,
    new_research,
)
from engine.research.state_machine import InvalidTransition, all_slots_locked, transition

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def locked_brief() -> ResearchBrief:
    return ResearchBrief(
        thesis=Slot("低波动量价回归", True),
        universe=Slot(
            Universe(
                market=Market.US,
                asset_class=AssetClass.EQUITY,
                underlying_asset_class=AssetClass.EQUITY,
                symbols=("AAPL", "MSFT"),
            ),
            True,
        ),
        max_effective_hours=Slot(12.0, True),
        round1_methods=Slot(
            (
                MethodRef("overfit.walk", "walk-v1"),
                MethodRef("stability.oos", "stability-v1"),
                MethodRef("crowding.load", "crowding-v1"),
                MethodRef("cost.turnover", "cost-v1"),
            ),
            True,
        ),
        coverage_floor=Slot(
            CoverageFloor(min_assets=2, min_years=10, max_missing_pct=5.0),
            True,
        ),
    )


def with_status(status: ResearchStatus):
    research = new_research("r-1", NOW)
    return replace(research, status=status, brief=locked_brief())


def test_confirm_run_is_a_draft_view_and_opens_version_one() -> None:
    research = replace(new_research("r-1", NOW), brief=locked_brief())
    assert research.status is ResearchStatus.DRAFT
    assert all_slots_locked(research.brief)

    running = transition(research, ResearchEvent.CONFIRM_RUN, NOW)

    assert running.status is ResearchStatus.RUNNING
    assert len(running.versions) == 1
    assert running.versions[0].number == 1
    assert running.versions[0].brief_snapshot == locked_brief()


@pytest.mark.parametrize(
    ("start", "event", "expected"),
    (
        (ResearchStatus.RUNNING, ResearchEvent.AUTO_CONTINUE, ResearchStatus.RUNNING),
        (ResearchStatus.RUNNING, ResearchEvent.PAUSE, ResearchStatus.PAUSED),
        (ResearchStatus.RUNNING, ResearchEvent.COMPLETE, ResearchStatus.COMPLETED),
        (ResearchStatus.RUNNING, ResearchEvent.BUDGET_EXHAUSTED, ResearchStatus.ENDED),
        (ResearchStatus.AWAITING_CONFIRM, ResearchEvent.CONFIRM_REJECT, ResearchStatus.RUNNING),
        (ResearchStatus.AWAITING_CONFIRM, ResearchEvent.CONFIRM_PAUSE, ResearchStatus.PAUSED),
        (ResearchStatus.PAUSED, ResearchEvent.RESUME, ResearchStatus.RUNNING),
        (ResearchStatus.COMPLETED, ResearchEvent.REVERIFY_PASS, ResearchStatus.COMPLETED),
        (ResearchStatus.COMPLETED, ResearchEvent.REVERIFY_FAIL, ResearchStatus.COMPLETED),
        (ResearchStatus.PAUSED, ResearchEvent.MODIFY_CONFIRM, ResearchStatus.RUNNING),
        (ResearchStatus.COMPLETED, ResearchEvent.MODIFY_CONFIRM, ResearchStatus.RUNNING),
        (ResearchStatus.ENDED, ResearchEvent.MODIFY_CONFIRM, ResearchStatus.RUNNING),
        (ResearchStatus.ENDED, ResearchEvent.EXTEND_CONFIRM, ResearchStatus.RUNNING),
    ),
)
def test_product_state_table(
    start: ResearchStatus,
    event: ResearchEvent,
    expected: ResearchStatus,
) -> None:
    research = with_status(start)
    assert transition(research, event, NOW).status is expected


@pytest.mark.parametrize("kind", (ConfirmKind.ECONOMIC, ConfirmKind.COVERAGE, ConfirmKind.REVIEW_BLOCKED))
def test_running_can_wait_without_opening_a_version(kind: ConfirmKind) -> None:
    research = with_status(ResearchStatus.RUNNING)
    request = ConfirmRequest(
        request_id=f"c-{kind.value}",
        kind=kind,
        proposed_change="保持同一版本等待人工判断",
        reason="自动研究不能安全继续",
        effect="确认后才会创建新版本",
    )

    waiting = transition(research, ResearchEvent.REQUEST_CONFIRM, NOW, request)

    assert waiting.status is ResearchStatus.AWAITING_CONFIRM
    assert waiting.pending_confirm == request
    assert waiting.versions == research.versions


def test_approval_applies_patch_and_opens_version_but_rejection_does_not() -> None:
    request = ConfirmRequest(
        "c-1",
        ConfirmKind.ECONOMIC,
        "改信号",
        "验证失败",
        "新版本",
        patch=(("thesis", "带拥挤过滤的低波动回归"),),
    )
    waiting = replace(
        with_status(ResearchStatus.AWAITING_CONFIRM),
        pending_confirm=request,
    )

    approved = transition(waiting, ResearchEvent.CONFIRM_APPROVE, NOW)
    rejected = transition(waiting, ResearchEvent.CONFIRM_REJECT, NOW)

    assert approved.status is ResearchStatus.RUNNING
    assert len(approved.versions) == 1
    assert approved.versions[0].number == 1
    assert approved.brief.thesis.value == "带拥挤过滤的低波动回归"
    assert approved.versions[0].confirmed_changes == request.patch
    assert rejected.status is ResearchStatus.RUNNING
    assert rejected.versions == waiting.versions


def test_wait_pause_complete_and_end_never_consume_time() -> None:
    for status in (
        ResearchStatus.DRAFT,
        ResearchStatus.AWAITING_CONFIRM,
        ResearchStatus.PAUSED,
        ResearchStatus.COMPLETED,
        ResearchStatus.ENDED,
    ):
        research = replace(with_status(status), effective_seconds=91.0)
        event = {
            ResearchStatus.DRAFT: ResearchEvent.EDIT_DRAFT,
            ResearchStatus.AWAITING_CONFIRM: ResearchEvent.WAIT,
            ResearchStatus.PAUSED: ResearchEvent.WAIT,
            ResearchStatus.COMPLETED: ResearchEvent.REVERIFY_PASS,
            ResearchStatus.ENDED: ResearchEvent.WAIT,
        }[status]
        assert transition(research, event, NOW).effective_seconds == 91.0


def test_invalid_transition_is_rejected() -> None:
    with pytest.raises(InvalidTransition, match="draft.*complete"):
        transition(with_status(ResearchStatus.DRAFT), ResearchEvent.COMPLETE, NOW)
