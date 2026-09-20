"""Tests for PIT consistency verifier and fourth export gate (B1)."""
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from engine.export import strategy_pack_eligibility
from engine.research.models import (
    Attempt,
    ChangeClass,
    Research,
    ResearchBrief,
    ResearchStatus,
    ReviewReport,
    Round,
    Slot,
    Version,
)
from engine.verifiers import (
    PIT_VERIFIER_REVISION,
    PitVerifierResult,
    VerificationReport,
    VerifierResult,
    _pit_consistency,
)


def test_pit_verifier_revision_is_preset() -> None:
    assert "pit.consistency" in PIT_VERIFIER_REVISION
    assert PIT_VERIFIER_REVISION["pit.consistency"]["category"] == "时点/前视一致性"


def test_pit_consistency_passes_when_all_evidence_before_cutoff() -> None:
    result = _pit_consistency(
        spec=None,
        evidence_timestamps=[
            ("ev-1", "2024-01-15"),
            ("ev-2", "2024-06-01"),
        ],
        backtest_cutoff="2024-12-31",
    )
    assert result.passed is True
    assert result.violations == ()
    assert result.verifier_id == "pit.consistency"


def test_pit_consistency_fails_when_evidence_after_cutoff() -> None:
    result = _pit_consistency(
        spec=None,
        evidence_timestamps=[
            ("ev-1", "2024-01-15"),
            ("ev-2", "2025-03-01"),
        ],
        backtest_cutoff="2024-12-31",
    )
    assert result.passed is False
    assert len(result.violations) == 1
    assert "ev-2" in result.violations[0]


def test_pit_consistency_empty_evidence_passes() -> None:
    result = _pit_consistency(
        spec=None,
        evidence_timestamps=[],
        backtest_cutoff="2024-12-31",
    )
    assert result.passed is True
    assert result.violations == ()


def test_pit_consistency_multiple_violations() -> None:
    result = _pit_consistency(
        spec=None,
        evidence_timestamps=[
            ("ev-1", "2025-01-01"),
            ("ev-2", "2025-02-01"),
            ("ev-3", "2024-06-01"),
        ],
        backtest_cutoff="2024-12-31",
    )
    assert result.passed is False
    assert len(result.violations) == 2
    assert any("ev-1" in v for v in result.violations)
    assert any("ev-2" in v for v in result.violations)


def _mock_attempt_with_pit(pit_passed: bool) -> Attempt:
    pit_result = PitVerifierResult(
        verifier_id="pit.consistency",
        revision="pit-v1",
        passed=pit_passed,
        values={"violations_count": 0.0 if pit_passed else 1.0},
        rule="test",
        evidence_timestamps=(),
        backtest_cutoff="2024-12-31",
        violations=() if pit_passed else ("ev-1 dated 2025-01-01 > cutoff 2024-12-31",),
    )
    scorecard = VerifierResult(
        verifier_id="scorecard.market",
        revision="scorecard-v1",
        passed=True,
        values={},
        rule="test",
    )
    return Attempt(
        attempt_id="a-1",
        number=1,
        change_class=ChangeClass.PARAM,
        spec=None,
        simulation=None,
        verification=VerificationReport(results=(scorecard, pit_result)),
        review=ReviewReport(passed=True, findings=()),
    )


def _completed_research_with_pit(pit_passed: bool) -> Research:
    now = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    attempt = _mock_attempt_with_pit(pit_passed)
    round_ = Round(
        round_id="v1-r1",
        number=1,
        accepted_attempt=attempt,
        completed_at=now,
    )
    version = Version(
        version_id="v-1",
        number=1,
        brief_snapshot=ResearchBrief(
            thesis=Slot("test", True),
            universe=Slot(None, True),
            max_effective_hours=Slot(12.0, True),
            round1_methods=Slot((), True),
            coverage_floor=Slot(None, True),
        ),
        rounds=(round_,),
        opened_at=now,
        opened_by="confirm_run",
    )
    return Research(
        research_id="r-1",
        status=ResearchStatus.COMPLETED,
        brief=ResearchBrief(),
        versions=(version,),
        current_version_number=1,
        pending_confirm=None,
        consecutive_review_failures=0,
        effective_seconds=3600.0,
        export_eligible=True,
        created_at=now,
        updated_at=now,
    )


def test_fourth_gate_pit_executed_and_passed_required() -> None:
    research_pit_passed = _completed_research_with_pit(pit_passed=True)
    research_pit_failed = _completed_research_with_pit(pit_passed=False)

    eligible = strategy_pack_eligibility(research_pit_passed)
    not_eligible = strategy_pack_eligibility(research_pit_failed)

    assert eligible.eligible is True
    assert "pit_executed_and_passed" not in eligible.failed_checks

    assert not_eligible.eligible is False
    assert "pit_executed_and_passed" in not_eligible.failed_checks


def test_fourth_gate_pit_not_executed() -> None:
    """Test that missing PIT verification fails the fourth gate."""
    now = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    scorecard = VerifierResult(
        verifier_id="scorecard.market",
        revision="scorecard-v1",
        passed=True,
        values={},
        rule="test",
    )
    attempt = Attempt(
        attempt_id="a-1",
        number=1,
        change_class=ChangeClass.PARAM,
        spec=None,
        simulation=None,
        verification=VerificationReport(results=(scorecard,)),
        review=ReviewReport(passed=True, findings=()),
    )
    round_ = Round(
        round_id="v1-r1",
        number=1,
        accepted_attempt=attempt,
        completed_at=now,
    )
    version = Version(
        version_id="v-1",
        number=1,
        brief_snapshot=ResearchBrief(
            thesis=Slot("test", True),
            universe=Slot(None, True),
            max_effective_hours=Slot(12.0, True),
            round1_methods=Slot((), True),
            coverage_floor=Slot(None, True),
        ),
        rounds=(round_,),
        opened_at=now,
        opened_by="confirm_run",
    )
    research = Research(
        research_id="r-1",
        status=ResearchStatus.COMPLETED,
        brief=ResearchBrief(),
        versions=(version,),
        current_version_number=1,
        pending_confirm=None,
        consecutive_review_failures=0,
        effective_seconds=3600.0,
        export_eligible=True,
        created_at=now,
        updated_at=now,
    )
    
    eligibility = strategy_pack_eligibility(research)
    assert eligibility.eligible is False
    assert "pit_executed_and_passed" in eligibility.failed_checks
