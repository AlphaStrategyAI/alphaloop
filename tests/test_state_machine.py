from dataclasses import replace
from datetime import UTC, datetime

import pytest

from engine.research.models import (
    AssetClass,
    ConfirmKind,
    ConfirmRequest,
    CoverageFloor,
    EvidenceKind,
    EvidenceRef,
    InvalidEvidenceRefError,
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


def test_confirm_kind_has_only_economic_and_coverage() -> None:
    assert set(ConfirmKind) == {ConfirmKind.ECONOMIC, ConfirmKind.COVERAGE}


def test_awaiting_modify_confirm_opens_a_version_from_user_patch() -> None:
    waiting = replace(
        with_status(ResearchStatus.AWAITING_CONFIRM),
        pending_confirm=ConfirmRequest(
            "c-engine",
            ConfirmKind.ECONOMIC,
            "改信号",
            "验证失败",
            "引擎提议",
            patch=(("thesis", Slot("引擎提议的原理", True)),),
        ),
        brief=replace(locked_brief(), thesis=Slot("用户改过的原理", True)),
    )

    running = transition(waiting, ResearchEvent.MODIFY_CONFIRM, NOW)

    assert running.status is ResearchStatus.RUNNING
    assert running.pending_confirm is None
    assert running.versions[-1].opened_by == "modified_settings_confirm"
    assert running.brief.thesis.value == "用户改过的原理"


def test_review_blocked_is_not_a_confirm_kind() -> None:
    assert not hasattr(ConfirmKind, "REVIEW_BLOCKED")
    assert "review_blocked" not in {kind.value for kind in ConfirmKind}


@pytest.mark.parametrize("kind", (ConfirmKind.ECONOMIC, ConfirmKind.COVERAGE))
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
    store = MockEvidenceStore({"a-1"})
    request = ConfirmRequest(
        "c-1",
        ConfirmKind.ECONOMIC,
        "改信号",
        "验证失败",
        "新版本",
        why_change=(
            EvidenceRef(
                record_id="a-1",
                recorded_at=datetime(2026, 8, 28, 10, 0, tzinfo=UTC),
                kind=EvidenceKind.ATTEMPT,
            ),
        ),
        created_at=datetime(2026, 8, 28, 11, 0, tzinfo=UTC),
        patch=(("thesis", "带拥挤过滤的低波动回归"),),
    )
    waiting = replace(
        with_status(ResearchStatus.AWAITING_CONFIRM),
        pending_confirm=request,
    )

    approved = transition(waiting, ResearchEvent.CONFIRM_APPROVE, NOW, store=store)
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


class MockEvidenceStore:
    """Mock store for B4 evidence validation integration tests."""
    def __init__(self, existing_ids: set[str]) -> None:
        self._existing = existing_ids

    def get_attempt(self, record_id: str) -> dict | None:
        return {"id": record_id} if record_id in self._existing else None

    def get_verification_report(self, record_id: str) -> dict | None:
        return {"id": record_id} if record_id in self._existing else None

    def get_round(self, record_id: str) -> dict | None:
        return {"id": record_id} if record_id in self._existing else None

    def get_simulation_report(self, record_id: str) -> dict | None:
        return {"id": record_id} if record_id in self._existing else None


def test_confirm_approve_with_valid_evidence_opens_version() -> None:
    """Integration test: CONFIRM_APPROVE with valid EvidenceRef opens new version."""
    store = MockEvidenceStore({"a-1"})
    request = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="改信号",
        reason="验证失败",
        effect="新版本",
        why_change=(
            EvidenceRef(
                record_id="a-1",
                recorded_at=datetime(2026, 8, 28, 10, 0, tzinfo=UTC),
                kind=EvidenceKind.ATTEMPT,
                summary="Sharpe下降",
            ),
        ),
        created_at=datetime(2026, 8, 28, 11, 0, tzinfo=UTC),
        patch=(("thesis", "带拥挤过滤的低波动回归"),),
    )
    waiting = replace(
        with_status(ResearchStatus.AWAITING_CONFIRM),
        pending_confirm=request,
    )

    approved = transition(waiting, ResearchEvent.CONFIRM_APPROVE, NOW, store=store)

    assert approved.status is ResearchStatus.RUNNING
    assert len(approved.versions) == 1
    assert approved.pending_confirm is None


def test_confirm_approve_with_empty_evidence_rejects() -> None:
    """Integration test: CONFIRM_APPROVE with empty why_change raises InvalidEvidenceRefError."""
    store = MockEvidenceStore(set())
    request = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="改信号",
        reason="验证失败",  # Has reason but no evidence
        effect="新版本",
        why_change=(),  # Empty!
        created_at=datetime(2026, 8, 28, 11, 0, tzinfo=UTC),
    )
    waiting = replace(
        with_status(ResearchStatus.AWAITING_CONFIRM),
        pending_confirm=request,
    )

    with pytest.raises(InvalidEvidenceRefError, match="at least one EvidenceRef"):
        transition(waiting, ResearchEvent.CONFIRM_APPROVE, NOW, store=store)

    # Status should NOT have changed
    assert waiting.status is ResearchStatus.AWAITING_CONFIRM


def test_confirm_approve_with_missing_evidence_rejects() -> None:
    """Integration test: CONFIRM_APPROVE with missing evidence record raises error."""
    store = MockEvidenceStore(set())  # No records exist
    request = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="改信号",
        reason="验证失败",
        effect="新版本",
        why_change=(
            EvidenceRef(
                record_id="nonexistent-attempt",
                recorded_at=datetime(2026, 8, 28, 10, 0, tzinfo=UTC),
                kind=EvidenceKind.ATTEMPT,
            ),
        ),
        created_at=datetime(2026, 8, 28, 11, 0, tzinfo=UTC),
    )
    waiting = replace(
        with_status(ResearchStatus.AWAITING_CONFIRM),
        pending_confirm=request,
    )

    with pytest.raises(InvalidEvidenceRefError, match="not found"):
        transition(waiting, ResearchEvent.CONFIRM_APPROVE, NOW, store=store)


def test_confirm_approve_with_future_evidence_rejects() -> None:
    """Integration test: CONFIRM_APPROVE with post-hoc evidence raises error."""
    store = MockEvidenceStore({"a-1"})
    request = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="改信号",
        reason="验证失败",
        effect="新版本",
        why_change=(
            EvidenceRef(
                record_id="a-1",
                recorded_at=datetime(2026, 8, 28, 14, 0, tzinfo=UTC),  # After created_at!
                kind=EvidenceKind.ATTEMPT,
            ),
        ),
        created_at=datetime(2026, 8, 28, 11, 0, tzinfo=UTC),
    )
    waiting = replace(
        with_status(ResearchStatus.AWAITING_CONFIRM),
        pending_confirm=request,
    )

    with pytest.raises(InvalidEvidenceRefError, match="not before"):
        transition(waiting, ResearchEvent.CONFIRM_APPROVE, NOW, store=store)


def test_confirm_approve_without_store_rejects() -> None:
    """CONFIRM_APPROVE without store MUST reject - fail closed (B4 iron rule)."""
    request = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="改信号",
        reason="验证失败",
        effect="新版本",
        why_change=(
            EvidenceRef(
                record_id="a-1",
                recorded_at=datetime(2026, 8, 28, 10, 0, tzinfo=UTC),
                kind=EvidenceKind.ATTEMPT,
            ),
        ),
        created_at=datetime(2026, 8, 28, 11, 0, tzinfo=UTC),
    )
    waiting = replace(
        with_status(ResearchStatus.AWAITING_CONFIRM),
        pending_confirm=request,
    )

    # Without store, MUST reject - no bypass allowed
    with pytest.raises(InvalidTransition, match="requires store"):
        transition(waiting, ResearchEvent.CONFIRM_APPROVE, NOW, store=None)


def test_confirm_approve_without_pending_confirm_rejects() -> None:
    """CONFIRM_APPROVE without pending_confirm MUST reject."""
    waiting = replace(
        with_status(ResearchStatus.AWAITING_CONFIRM),
        pending_confirm=None,
    )

    with pytest.raises(InvalidTransition, match="requires pending_confirm"):
        transition(waiting, ResearchEvent.CONFIRM_APPROVE, NOW, store=MockEvidenceStore(set()))
