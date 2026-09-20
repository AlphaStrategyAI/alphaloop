"""Tests for B4: Evidence-ID validation and fifth confirm prompt."""
from datetime import UTC, datetime

import pytest

from engine.research.models import (
    ConfirmKind,
    ConfirmRequest,
    EvidenceKind,
    EvidenceRef,
    InvalidEvidenceRefError,
    assert_preconfirm_evidence,
)


def test_evidence_ref_fields() -> None:
    ref = EvidenceRef(
        record_id="a-123",
        recorded_at=datetime(2026, 9, 15, 10, 0, tzinfo=UTC),
        kind=EvidenceKind.ATTEMPT,
        summary="验证显示Sharpe=1.2，超额收益5%",
    )
    assert ref.record_id == "a-123"
    assert ref.kind == EvidenceKind.ATTEMPT


def test_evidence_kind_values() -> None:
    assert EvidenceKind.ATTEMPT == "attempt"
    assert EvidenceKind.ROUND == "round"
    assert EvidenceKind.VERIFICATION_REPORT == "verification_report"
    assert EvidenceKind.SIMULATION_REPORT == "simulation_report"


def test_confirm_request_with_why_change_evidence() -> None:
    evidence = (
        EvidenceRef(
            record_id="a-1",
            recorded_at=datetime(2026, 9, 15, 10, 0, tzinfo=UTC),
            kind=EvidenceKind.ATTEMPT,
            summary="原信号不稳定",
        ),
        EvidenceRef(
            record_id="v-r1",
            recorded_at=datetime(2026, 9, 15, 11, 0, tzinfo=UTC),
            kind=EvidenceKind.VERIFICATION_REPORT,
            summary="Sharpe衰减50%",
        ),
    )
    request = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="改信号机制",
        reason="验证显示原信号不稳定",
        effect="开新版本",
        why_change=evidence,
        created_at=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
    )
    assert len(request.why_change) == 2
    assert all(ref.recorded_at < request.created_at for ref in request.why_change)


class MockStore:
    """Mock store for testing evidence validation."""
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


def test_assert_preconfirm_evidence_passes_for_valid_refs() -> None:
    store = MockStore({"a-1", "v-r1"})
    request = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="test",
        reason="test",
        effect="test",
        why_change=(
            EvidenceRef("a-1", datetime(2026, 9, 15, 10, 0, tzinfo=UTC), EvidenceKind.ATTEMPT),
        ),
        created_at=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
    )
    assert_preconfirm_evidence(request, store)


def test_assert_preconfirm_evidence_rejects_missing_ref() -> None:
    store = MockStore(set())
    request = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="test",
        reason="test",
        effect="test",
        why_change=(
            EvidenceRef("nonexistent", datetime(2026, 9, 15, 10, 0, tzinfo=UTC), EvidenceKind.ATTEMPT),
        ),
        created_at=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
    )
    with pytest.raises(InvalidEvidenceRefError, match="not found"):
        assert_preconfirm_evidence(request, store)


def test_assert_preconfirm_evidence_rejects_future_ref() -> None:
    store = MockStore({"a-1"})
    request = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="test",
        reason="test",
        effect="test",
        why_change=(
            EvidenceRef("a-1", datetime(2026, 9, 15, 14, 0, tzinfo=UTC), EvidenceKind.ATTEMPT),
        ),
        created_at=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
    )
    with pytest.raises(InvalidEvidenceRefError, match="not before"):
        assert_preconfirm_evidence(request, store)


def test_assert_preconfirm_evidence_rejects_same_time_ref() -> None:
    """Evidence recorded at the exact same time as request creation is invalid."""
    store = MockStore({"a-1"})
    same_time = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
    request = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="test",
        reason="test",
        effect="test",
        why_change=(
            EvidenceRef("a-1", same_time, EvidenceKind.ATTEMPT),
        ),
        created_at=same_time,
    )
    with pytest.raises(InvalidEvidenceRefError, match="not before"):
        assert_preconfirm_evidence(request, store)


def test_assert_preconfirm_evidence_requires_created_at() -> None:
    """ConfirmRequest must have created_at for evidence validation."""
    store = MockStore({"a-1"})
    request = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="test",
        reason="test",
        effect="test",
        why_change=(
            EvidenceRef("a-1", datetime(2026, 9, 15, 10, 0, tzinfo=UTC), EvidenceKind.ATTEMPT),
        ),
        created_at=None,
    )
    with pytest.raises(InvalidEvidenceRefError, match="must have created_at"):
        assert_preconfirm_evidence(request, store)


def test_confirm_request_who_pays_optional() -> None:
    request = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="改信号机制",
        reason="验证显示原信号不稳定",
        effect="开新版本",
        why_change=(),
        who_pays_optional=None,
        created_at=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
    )
    assert request.who_pays_optional is None

    request_answered = ConfirmRequest(
        request_id="c-2",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="增加动量因子",
        reason="回测显示有alpha",
        effect="开新版本",
        why_change=(),
        who_pays_optional="赚的是趋势跟随者追涨杀跌的钱，对方会继续付因为行为偏差持续存在",
        created_at=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
    )
    assert request_answered.who_pays_optional is not None


def test_empty_why_change_passes_validation() -> None:
    """Empty why_change is allowed (no evidence cited)."""
    store = MockStore(set())
    request = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="test",
        reason="test",
        effect="test",
        why_change=(),
        created_at=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
    )
    assert_preconfirm_evidence(request, store)
