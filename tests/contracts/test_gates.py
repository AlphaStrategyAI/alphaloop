from __future__ import annotations

import pytest

from alphaloop.contracts.gates import (
    GateEvidence,
    GateResult,
    HardGateName,
    IncompleteEvidenceError,
    evaluate_hard_gates,
    evidence_from_dict,
    evidence_to_dict,
    outcome_from_evidence,
)
from alphaloop.contracts.status import JobStatus, ResearchOutcome


REQUIRED = (
    HardGateName.DSR,
    HardGateName.WALK_FORWARD,
    HardGateName.VS_RANDOM,
    HardGateName.VS_BUY_HOLD,
    HardGateName.VS_BENCHMARK,
    HardGateName.DATA_CONSISTENCY,
)


def _all_pass() -> tuple[GateResult, ...]:
    return tuple(GateResult(name=name, passed=True, detail={}) for name in REQUIRED)


def test_llm_judge_is_not_a_hard_gate():
    names = {item.value for item in HardGateName}
    assert "llm_judge" not in names
    assert "judge" not in names


def test_missing_required_gate_raises():
    partial = _all_pass()[:-1]
    with pytest.raises(IncompleteEvidenceError):
        evaluate_hard_gates(REQUIRED, partial)


def test_complete_pass_is_found_when_job_completed():
    evidence = evaluate_hard_gates(REQUIRED, _all_pass())
    assert (
        outcome_from_evidence(JobStatus.COMPLETED, evidence)
        is ResearchOutcome.FOUND
    )


def test_one_failure_is_no_evidence():
    rows = list(_all_pass())
    rows[REQUIRED.index(HardGateName.VS_BENCHMARK)] = GateResult(
        name=HardGateName.VS_BENCHMARK, passed=False, detail={}
    )
    evidence = evaluate_hard_gates(REQUIRED, tuple(rows))
    assert (
        outcome_from_evidence(JobStatus.COMPLETED, evidence)
        is ResearchOutcome.NO_EVIDENCE
    )


def test_empty_required_cannot_produce_found():
    with pytest.raises((IncompleteEvidenceError, ValueError)):
        evaluate_hard_gates((), ())
    evidence = GateEvidence(results=(), required=())
    assert evidence.all_passed is False
    assert (
        outcome_from_evidence(JobStatus.COMPLETED, evidence)
        is not ResearchOutcome.FOUND
    )


def test_duplicate_gate_results_do_not_last_write_win():
    rows = (
        GateResult(name=HardGateName.DSR, passed=False, detail={}),
        GateResult(name=HardGateName.DSR, passed=True, detail={}),
    )
    with pytest.raises((IncompleteEvidenceError, ValueError)):
        evaluate_hard_gates((HardGateName.DSR,), rows)


def test_evidence_dict_round_trip():
    evidence = evaluate_hard_gates(REQUIRED, _all_pass())
    assert evidence_from_dict(evidence_to_dict(evidence)) == evidence
