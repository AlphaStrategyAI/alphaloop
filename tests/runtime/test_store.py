from __future__ import annotations

import dataclasses

import pytest
import yaml

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.research_spec import ResearchSpec, new_research_spec
from alphaloop.contracts.status import JobStatus, ResearchOutcome
from alphaloop.runtime.store import JobRecord, JobStore, new_run_id


def _spec() -> ResearchSpec:
    return new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="12-1 momentum",
        market_scope="US large-cap equities",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward", "vs_benchmark"),
        seed=7,
        time_budget_s=3600,
        cost_budget_usd=5.0,
    )


def test_create_returns_queued_none_immediately(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    assert job.status is JobStatus.QUEUED
    assert job.research_outcome is ResearchOutcome.NONE
    assert job.run_id.startswith("j_")
    assert job.recovery_attempts == 0
    loaded = store.get(job.run_id)
    assert loaded == job


def test_create_writes_research_spec_yaml(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    spec = _spec()
    job = store.create(spec)
    layout = RunLayout(tmp_path / job.run_id)
    payload = yaml.safe_load(layout.research_spec.read_text(encoding="utf-8"))
    assert ResearchSpec.from_dict(payload) == spec


def test_missing_job_raises_keyerror(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    with pytest.raises(KeyError):
        store.get("j_missing")


def test_update_status_persists_and_sets_inconclusive_on_failed(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    updated = store.update_status(job.run_id, JobStatus.FAILED, error="worker crashed")
    assert updated.status is JobStatus.FAILED
    assert updated.research_outcome is ResearchOutcome.INCONCLUSIVE
    assert updated.error == "worker crashed"
    assert store.get(job.run_id) == updated


def test_completed_without_evidence_is_inconclusive(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    updated = store.update_status(job.run_id, JobStatus.COMPLETED)
    assert updated.status is JobStatus.COMPLETED
    assert updated.research_outcome is ResearchOutcome.INCONCLUSIVE


def test_job_record_is_frozen():
    assert dataclasses.is_dataclass(JobRecord)
    assert JobRecord.__dataclass_params__.frozen is True


def test_new_run_id_is_unique():
    ids = {new_run_id() for _ in range(50)}
    assert len(ids) == 50
    assert all(item.startswith("j_") for item in ids)


def test_increment_recovery_and_heartbeat(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    beat = store.set_heartbeat(job.run_id, pid=4242, at="2026-08-19T00:00:00+00:00")
    assert beat.worker_pid == 4242
    assert beat.heartbeat_at == "2026-08-19T00:00:00+00:00"
    again = store.increment_recovery(job.run_id)
    assert again.recovery_attempts == 1
