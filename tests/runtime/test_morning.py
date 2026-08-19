from __future__ import annotations

import json

from alphaloop.contracts.gates import (
    GateResult,
    HardGateName,
    evidence_to_dict,
    evaluate_hard_gates,
)
from alphaloop.contracts.status import ResearchOutcome
from alphaloop.runtime.morning import (
    STOP_REASON_ALL_GATES_PASSED,
    STOP_REASON_HARD_GATE_FAILED,
    STOP_REASON_INCOMPLETE_EVIDENCE,
    morning_view,
)
from alphaloop.runtime.store import JobStore
from tests.runtime.test_supervisor import _spec


def _gates_for(spec, *, fail_first: bool = False):
    required = tuple(HardGateName(name) for name in spec.success_criteria.hard_gates)
    rows = []
    for i, name in enumerate(required):
        ok = not (fail_first and i == 0)
        rows.append(GateResult(name=name, passed=ok, detail={}))
    return evaluate_hard_gates(required, tuple(rows))


def test_missing_gates_is_inconclusive(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    done = store.complete_from_artifacts(job.run_id)
    view = morning_view(done, tmp_path)
    assert view["research_outcome"] == ResearchOutcome.INCONCLUSIVE.value
    assert view["evidence"] is None
    assert view["stop_reason"] == STOP_REASON_INCOMPLETE_EVIDENCE
    assert view["funnel"]["dominant_failures"] == []
    assert view["queued_hypotheses"] == []


def test_passing_gates_found(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    evidence = _gates_for(job.spec)
    evidence_dir = tmp_path / job.run_id / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    done = store.complete_from_artifacts(job.run_id)
    view = morning_view(done, tmp_path)
    assert view["research_outcome"] == ResearchOutcome.FOUND.value
    assert view["stop_reason"] == STOP_REASON_ALL_GATES_PASSED
    assert view["evidence"]["all_passed"] is True
    assert view["funnel"]["dominant_failures"] == []
    assert view["hypothesis"]["signal_mechanism"] == "momentum_12_1"


def test_failed_gate_is_no_evidence(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    evidence = _gates_for(job.spec, fail_first=True)
    evidence_dir = tmp_path / job.run_id / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    done = store.complete_from_artifacts(job.run_id)
    view = morning_view(done, tmp_path)
    assert view["research_outcome"] == ResearchOutcome.NO_EVIDENCE.value
    assert view["stop_reason"] == STOP_REASON_HARD_GATE_FAILED
    assert view["funnel"]["dominant_failures"] == [job.spec.success_criteria.hard_gates[0]]


def test_corrupt_gates_does_not_claim_found(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    evidence_dir = tmp_path / job.run_id / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "gates.json").write_text("{not-json")
    done = store.complete_from_artifacts(job.run_id)
    view = morning_view(done, tmp_path)
    assert view["research_outcome"] != ResearchOutcome.FOUND.value
    assert view["evidence"] is None


def test_revisions_and_queued_hypotheses(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    run_dir = tmp_path / job.run_id
    (run_dir / "trial-ledger.jsonl").write_text(
        json.dumps({"trial_id": "c_1", "revision": "none"}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "recommendations.json").write_text(
        json.dumps({"queued_hypotheses": [{"statement": "try mean reversion"}]}),
        encoding="utf-8",
    )
    view = morning_view(store.get(job.run_id), tmp_path)
    assert view["revisions"][0]["trial_id"] == "c_1"
    assert view["queued_hypotheses"][0]["statement"] == "try mean reversion"
    assert view["research_outcome"] == ResearchOutcome.NONE.value
    assert view["stop_reason"] is None
