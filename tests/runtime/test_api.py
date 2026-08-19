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


def test_get_cancel_resume(tmp_path):
    api = _api(tmp_path)
    created = api.create_run(_spec())
    run_id = created["run_id"]
    api.supervisor.tick()
    assert api.get_run(run_id)["status"] == JobStatus.RUNNING.value
    cancelled = api.cancel_run(run_id)
    assert cancelled["status"] == JobStatus.CANCELLED.value
    assert cancelled["research_outcome"] == ResearchOutcome.INCONCLUSIVE.value
    with pytest.raises(ValueError):
        api.resume_run(run_id)
