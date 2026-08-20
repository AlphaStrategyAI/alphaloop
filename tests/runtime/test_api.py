from __future__ import annotations

import pytest

from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.contracts.status import JobStatus, ResearchOutcome
from alphaloop.runtime.api import JobAPI, PreflightRejected
from alphaloop.runtime.preflight import HOST_CONSTRAINT
from alphaloop.runtime.store import JobStore
from alphaloop.runtime.supervisor import Supervisor
from tests.runtime.test_supervisor import FakeWorker, _cached_spec


def _api(tmp_path) -> JobAPI:
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, heartbeat_timeout_s=60.0)
    return JobAPI(store, sup, tmp_path)


def test_create_run_returns_immediately_without_starting_worker(tmp_path):
    api = _api(tmp_path)
    payload = api.create_run(_cached_spec())
    assert payload["status"] == JobStatus.QUEUED.value
    assert payload["research_outcome"] == ResearchOutcome.NONE.value
    assert payload["host_constraint"] == HOST_CONSTRAINT
    assert payload["run_id"].startswith("j_")
    assert api.supervisor.worker.spawned == []


def test_list_jobs_includes_research_outcome(tmp_path):
    api = _api(tmp_path)
    created = api.create_run(_cached_spec())
    listed = api.list_jobs()
    assert listed["jobs"][0]["run_id"] == created["run_id"]
    assert listed["jobs"][0]["research_outcome"] == ResearchOutcome.NONE.value
    assert listed["jobs"][0]["hypothesis"]["signal_mechanism"] == "momentum_12_1"
    assert listed["jobs"][0]["seed"] == created["seed"]
    assert listed["jobs"][0]["n_trials"] == 0


def test_get_run_includes_sealed_evidence(tmp_path):
    import json

    from alphaloop.contracts.gates import (
        GateResult,
        HardGateName,
        evidence_to_dict,
        evaluate_hard_gates,
    )

    api = _api(tmp_path)
    created = api.create_run(_cached_spec())
    run_id = created["run_id"]
    job = api.store.get(run_id)
    required = tuple(HardGateName(name) for name in job.spec.success_criteria.hard_gates)
    evidence = evaluate_hard_gates(
        required,
        tuple(GateResult(name=name, passed=True, detail={}) for name in required),
    )
    evidence_dir = tmp_path / run_id / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    api.store.complete_from_artifacts(run_id)
    payload = api.get_run(run_id)
    assert payload["research_outcome"] == ResearchOutcome.FOUND.value
    assert payload["evidence"]["all_passed"] is True
    assert payload["stop_reason"] == "all_gates_passed"
    assert payload["seed"] == job.spec.seed
    assert payload["n_trials"] == 0


def _seal_found(api, run_id: str, candidate_id: str = "c1") -> None:
    import json

    from alphaloop.contracts.gates import (
        GateResult,
        HardGateName,
        evidence_to_dict,
        evaluate_hard_gates,
    )

    job = api.store.get(run_id)
    required = tuple(HardGateName(name) for name in job.spec.success_criteria.hard_gates)
    evidence = evaluate_hard_gates(
        required,
        tuple(GateResult(name=name, passed=True, detail={}) for name in required),
    )
    evidence_dir = api.data_dir / run_id / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    (api.data_dir / run_id / "trial-ledger.jsonl").write_text(
        json.dumps(
            {
                "trial_id": candidate_id,
                "kind": "momentum_12_1",
                "parameters": {},
                "revision": "none",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    api.store.complete_from_artifacts(run_id)


def test_export_run_writes_asb_for_found_ledger_id(tmp_path):
    import zipfile

    from alphaloop.contracts.bundle import ExportNotAllowed

    api = _api(tmp_path)
    run_id = api.create_run(_cached_spec())["run_id"]
    _seal_found(api, run_id)
    payload = api.export_run(run_id, "c1")
    path = tmp_path / run_id / "exports" / "c1.asb"
    assert payload["exported_path"] == str(path)
    assert payload["exported_candidate_id"] == "c1"
    assert zipfile.is_zipfile(path)
    with pytest.raises(ValueError):
        api.export_run(run_id, "../escape")


def test_export_run_rejects_non_found(tmp_path):
    from alphaloop.contracts.bundle import ExportNotAllowed

    api = _api(tmp_path)
    run_id = api.create_run(_cached_spec())["run_id"]
    with pytest.raises(ExportNotAllowed):
        api.export_run(run_id, "c1")


def test_create_run_rejects_empty_gates_without_inserting_job(tmp_path):
    api = _api(tmp_path)
    spec = new_research_spec(
        statement="x",
        economic_logic="x",
        signal_mechanism="x",
        market_scope="x",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=(),
        seed=1,
        time_budget_s=10,
        cost_budget_usd=1.0,
    )
    with pytest.raises(PreflightRejected):
        api.create_run(spec)
    assert api.store.list_jobs() == ()


def test_cancelled_run_cannot_be_resumed(tmp_path):
    api = _api(tmp_path)
    created = api.create_run(_cached_spec())
    run_id = created["run_id"]
    api.supervisor.tick()
    assert api.get_run(run_id)["status"] == JobStatus.RUNNING.value
    cancelled = api.cancel_run(run_id)
    assert cancelled["status"] == JobStatus.CANCELLED.value
    assert cancelled["research_outcome"] == ResearchOutcome.INCONCLUSIVE.value
    terminated_after_cancel = list(api.supervisor.worker.terminated)
    assert len(terminated_after_cancel) == 1

    with pytest.raises(ValueError):
        api.resume_run(run_id)

    assert api.supervisor.worker.terminated == terminated_after_cancel


def test_resume_running_terminates_worker_and_requeues_until_tick(tmp_path):
    api = _api(tmp_path)
    run_id = api.create_run(_cached_spec())["run_id"]
    api.supervisor.tick()
    running = api.store.get(run_id)
    pid = running.worker_pid
    assert pid is not None
    spawned_before_resume = list(api.supervisor.worker.spawned)

    resumed = api.resume_run(run_id)

    assert api.supervisor.worker.terminated == [pid]
    assert api.supervisor.worker.spawned == spawned_before_resume
    assert resumed["status"] == JobStatus.QUEUED.value
    queued = api.store.get(run_id)
    assert queued.status is JobStatus.QUEUED
    assert queued.worker_pid is None


def test_resume_running_serializes_requeue_before_replacement_tick(
    tmp_path, monkeypatch
):
    api = _api(tmp_path)
    run_id = api.create_run(_cached_spec())["run_id"]
    api.supervisor.tick()
    running = api.store.get(run_id)
    old_pid = running.worker_pid
    assert old_pid is not None
    lifecycle_lock = api.supervisor.lifecycle_lock
    original_get = api.store.get
    original_requeue = api.store.requeue_unless_terminal

    def get_while_locked(requested_run_id):
        assert lifecycle_lock.locked()
        return original_get(requested_run_id)

    def requeue_while_locked(requested_run_id, expected_pid=None):
        assert lifecycle_lock.locked()
        return original_requeue(requested_run_id, expected_pid)

    with monkeypatch.context() as patch:
        patch.setattr(api.store, "get", get_while_locked)
        patch.setattr(api.store, "requeue_unless_terminal", requeue_while_locked)
        resumed = api.resume_run(run_id)

    assert resumed["status"] == JobStatus.QUEUED.value
    assert old_pid not in api.supervisor.worker.running
    assert api.supervisor.worker.running == {}

    api.supervisor.tick()

    replacement = api.store.get(run_id)
    assert replacement.status is JobStatus.RUNNING
    assert replacement.worker_pid != old_pid
    assert list(api.supervisor.worker.running) == [replacement.worker_pid]


def test_resume_failed_requeues_and_clears_error(tmp_path):
    api = _api(tmp_path)
    run_id = api.create_run(_cached_spec())["run_id"]
    api.store.update_status(run_id, JobStatus.FAILED, error="worker crashed")

    resumed = api.resume_run(run_id)

    assert resumed["status"] == JobStatus.QUEUED.value
    assert resumed["research_outcome"] == ResearchOutcome.NONE.value
    assert resumed["error"] is None


def test_preview_run_does_not_create_a_job(tmp_path):
    from alphaloop.protocol.search import method_parameter_grid

    api = _api(tmp_path)
    spec = _cached_spec()
    preview = api.preview_run(spec)
    grid = list(method_parameter_grid(spec.hypothesis.signal_mechanism))
    assert preview["ok"] is True
    assert preview["errors"] == []
    assert preview["spec_id"] == spec.spec_id
    assert preview["seed"] == spec.seed
    assert preview["statement"] == spec.hypothesis.statement
    assert preview["signal_mechanism"] == spec.hypothesis.signal_mechanism
    assert preview["hard_gates"] == list(spec.success_criteria.hard_gates)
    assert preview["method_parameter_grid"] == grid
    assert preview["planned_n_trials"] == len(grid)
    assert preview["time_budget_s"] == spec.time_budget_s
    assert preview["cost_budget_usd"] == spec.cost_budget_usd
    assert preview["host_constraint"] == HOST_CONSTRAINT
    assert "run_id" not in preview
    assert api.list_jobs()["jobs"] == []
    assert api.supervisor.worker.spawned == []


def test_preview_run_preflight_failure_is_not_ok(tmp_path):
    api = _api(tmp_path)
    spec = new_research_spec(
        statement="x",
        economic_logic="x",
        signal_mechanism="momentum_12_1",
        market_scope="x",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=(),
        seed=1,
        time_budget_s=10,
        cost_budget_usd=1.0,
    )
    preview = api.preview_run(spec)
    assert preview["ok"] is False
    assert preview["errors"]


def test_preview_run_rejects_parkinson_signal(tmp_path):
    api = _api(tmp_path)
    spec = new_research_spec(
        statement="x",
        economic_logic="x",
        signal_mechanism="parkinson_hist_vol",
        market_scope="AAPL",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr",),
        seed=1,
        time_budget_s=10,
        cost_budget_usd=1.0,
    )
    preview = api.preview_run(spec)
    assert preview["ok"] is False
    assert any("feature" in err.lower() for err in preview["errors"])
    assert api.list_jobs()["jobs"] == []
    assert "run_id" not in preview
    assert api.list_jobs()["jobs"] == []
