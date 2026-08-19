from __future__ import annotations

import json

from alphaloop.contracts.gates import (
    GateResult,
    HardGateName,
    evidence_to_dict,
    evaluate_hard_gates,
)
from alphaloop.contracts.status import JobStatus, ResearchOutcome
from alphaloop.runtime.store import JobStore
from tests.runtime.test_supervisor import FakeWorker, _spec
from alphaloop.runtime.supervisor import Supervisor


def test_complete_without_gates_is_inconclusive(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    done = store.complete_from_artifacts(job.run_id)
    assert done.status is JobStatus.COMPLETED
    assert done.research_outcome is ResearchOutcome.INCONCLUSIVE


def test_complete_with_passing_gates_is_found(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    required = tuple(HardGateName(name) for name in job.spec.success_criteria.hard_gates)
    evidence = evaluate_hard_gates(
        required,
        tuple(GateResult(name=name, passed=True, detail={}) for name in required),
    )
    evidence_dir = tmp_path / job.run_id / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    done = store.complete_from_artifacts(job.run_id)
    assert done.research_outcome is ResearchOutcome.FOUND
    assert done.sealed_outcome is ResearchOutcome.FOUND


def test_supervisor_exit_zero_reads_artifacts(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker)
    job = store.create(_spec())
    required = tuple(HardGateName(name) for name in job.spec.success_criteria.hard_gates)
    evidence = evaluate_hard_gates(
        required,
        tuple(GateResult(name=name, passed=True, detail={}) for name in required),
    )
    evidence_dir = tmp_path / job.run_id / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    sup.tick()
    pid = store.get(job.run_id).worker_pid
    worker.succeed(pid)
    sup.tick()
    done = store.get(job.run_id)
    assert done.status is JobStatus.COMPLETED
    assert done.research_outcome is ResearchOutcome.FOUND
