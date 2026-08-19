from __future__ import annotations

import pytest

from alphaloop.contracts.status import (
    JobStatus,
    ResearchOutcome,
    derive_research_outcome,
)


def test_running_has_no_research_outcome():
    assert (
        derive_research_outcome(
            JobStatus.RUNNING,
            evidence_complete=False,
            all_gates_passed=False,
        )
        is ResearchOutcome.NONE
    )


def test_completed_all_pass_is_found():
    assert (
        derive_research_outcome(
            JobStatus.COMPLETED,
            evidence_complete=True,
            all_gates_passed=True,
        )
        is ResearchOutcome.FOUND
    )


def test_completed_any_fail_is_no_evidence():
    assert (
        derive_research_outcome(
            JobStatus.COMPLETED,
            evidence_complete=True,
            all_gates_passed=False,
        )
        is ResearchOutcome.NO_EVIDENCE
    )


def test_completed_incomplete_evidence_is_inconclusive():
    assert (
        derive_research_outcome(
            JobStatus.COMPLETED,
            evidence_complete=False,
            all_gates_passed=True,
        )
        is ResearchOutcome.INCONCLUSIVE
    )


@pytest.mark.parametrize(
    "status, complete, passed, expected",
    [
        (JobStatus.QUEUED, False, False, ResearchOutcome.NONE),
        (JobStatus.QUEUED, True, True, ResearchOutcome.NONE),
        (JobStatus.RUNNING, False, False, ResearchOutcome.NONE),
        (JobStatus.RUNNING, True, True, ResearchOutcome.NONE),
        (JobStatus.COMPLETED, True, True, ResearchOutcome.FOUND),
        (JobStatus.COMPLETED, True, False, ResearchOutcome.NO_EVIDENCE),
        (JobStatus.COMPLETED, False, True, ResearchOutcome.INCONCLUSIVE),
        (JobStatus.COMPLETED, False, False, ResearchOutcome.INCONCLUSIVE),
        (JobStatus.FAILED, True, True, ResearchOutcome.INCONCLUSIVE),
        (JobStatus.FAILED, True, False, ResearchOutcome.INCONCLUSIVE),
        (JobStatus.FAILED, False, False, ResearchOutcome.INCONCLUSIVE),
        (JobStatus.CANCELLED, True, False, ResearchOutcome.INCONCLUSIVE),
        (JobStatus.CANCELLED, False, True, ResearchOutcome.INCONCLUSIVE),
    ],
)
def test_status_outcome_matrix(status, complete, passed, expected):
    assert (
        derive_research_outcome(status, complete, passed)
        is expected
    )


def test_cancelled_cannot_claim_found_without_seal():
    assert (
        derive_research_outcome(
            JobStatus.CANCELLED,
            evidence_complete=True,
            all_gates_passed=True,
        )
        is ResearchOutcome.INCONCLUSIVE
    )


@pytest.mark.parametrize("status", [JobStatus.FAILED, JobStatus.CANCELLED])
def test_failed_or_cancelled_cannot_claim_found(status):
    assert (
        derive_research_outcome(
            status,
            evidence_complete=True,
            all_gates_passed=True,
        )
        is ResearchOutcome.INCONCLUSIVE
    )


def test_sealed_found_survives_cancel():
    assert (
        derive_research_outcome(
            JobStatus.CANCELLED,
            evidence_complete=True,
            all_gates_passed=True,
            sealed=ResearchOutcome.FOUND,
        )
        is ResearchOutcome.FOUND
    )


def test_sealed_found_requires_complete_evidence():
    assert (
        derive_research_outcome(
            JobStatus.CANCELLED,
            evidence_complete=False,
            all_gates_passed=True,
            sealed=ResearchOutcome.FOUND,
        )
        is ResearchOutcome.INCONCLUSIVE
    )


def test_job_status_string_coercion():
    assert (
        derive_research_outcome(
            "completed",
            evidence_complete=True,
            all_gates_passed=True,
        )
        is ResearchOutcome.FOUND
    )


def test_incomplete_evidence_cannot_use_all_gates_passed_shortcut():
    outcome = derive_research_outcome(
        JobStatus.COMPLETED,
        evidence_complete=False,
        all_gates_passed=True,
    )
    assert outcome is not ResearchOutcome.FOUND
