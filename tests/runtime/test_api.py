from __future__ import annotations

import pytest

from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.contracts.status import JobStatus, ResearchOutcome
from alphaloop.runtime.api import JobAPI, PreflightRejected
from alphaloop.runtime.preflight import HOST_CONSTRAINT
from alphaloop.runtime.store import JobStore
from alphaloop.runtime.supervisor import Supervisor
from tests.runtime.test_supervisor import FakeWorker, _spec


def _api(tmp_path) -> JobAPI:
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, heartbeat_timeout_s=60.0)
    return JobAPI(store, sup, tmp_path)


def test_create_run_returns_immediately_without_starting_worker(tmp_path):
    api = _api(tmp_path)
    payload = api.create_run(_spec())
    assert payload["status"] == JobStatus.QUEUED.value
    assert payload["research_outcome"] == ResearchOutcome.NONE.value
    assert payload["host_constraint"] == HOST_CONSTRAINT
    assert payload["run_id"].startswith("j_")
    assert api.supervisor.worker.spawned == []


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
    created = api.create_run(_spec())
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
    run_id = api.create_run(_spec())["run_id"]
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
    run_id = api.create_run(_spec())["run_id"]
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
    run_id = api.create_run(_spec())["run_id"]
    api.store.update_status(run_id, JobStatus.FAILED, error="worker crashed")

    resumed = api.resume_run(run_id)

    assert resumed["status"] == JobStatus.QUEUED.value
    assert resumed["research_outcome"] == ResearchOutcome.NONE.value
    assert resumed["error"] is None
