from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.contracts.status import JobStatus, ResearchOutcome
from alphaloop.runtime.checkpoint import write_heartbeat
from alphaloop.runtime.store import JobStore
from alphaloop.runtime.supervisor import Supervisor


def _spec():
    return new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward", "vs_benchmark"),
        seed=7,
        time_budget_s=3600,
        cost_budget_usd=5.0,
    )


class FakeWorker:
    def __init__(self, *, write_heartbeat_on_spawn: bool = True) -> None:
        self.running: Dict[int, str] = {}
        self.exit_codes: Dict[int, int] = {}
        self.spawned: list[str] = []
        self.terminated: list[int] = []
        self.write_heartbeat_on_spawn = write_heartbeat_on_spawn
        self._next_pid = 1000

    def spawn(self, run_id: str, data_dir: Path) -> int:
        pid = self._next_pid
        self._next_pid += 1
        self.running[pid] = run_id
        self.spawned.append(run_id)
        if self.write_heartbeat_on_spawn:
            layout = RunLayout(Path(data_dir) / run_id)
            layout.run_dir.mkdir(parents=True, exist_ok=True)
            write_heartbeat(layout, pid=pid, at="2026-08-19T00:00:00+00:00")
        return pid

    def poll(self, pid: int, run_id: Optional[str] = None) -> Optional[int]:
        if run_id is not None and self.running.get(pid, run_id) != run_id:
            return 1
        if pid in self.exit_codes:
            return self.exit_codes[pid]
        if pid in self.running:
            return None
        return 1

    def terminate(self, pid: int, run_id: Optional[str] = None) -> None:
        if run_id is not None and self.running.get(pid, run_id) != run_id:
            return
        self.terminated.append(pid)
        self.running.pop(pid, None)
        self.exit_codes[pid] = -15

    def crash(self, pid: int) -> None:
        self.running.pop(pid, None)
        self.exit_codes[pid] = 1

    def succeed(self, pid: int) -> None:
        self.running.pop(pid, None)
        self.exit_codes[pid] = 0


def test_tick_starts_queued_job(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, heartbeat_timeout_s=60.0)
    job = store.create(_spec())
    sup.tick()
    running = store.get(job.run_id)
    assert running.status is JobStatus.RUNNING
    assert running.research_outcome is ResearchOutcome.NONE
    assert worker.spawned == [job.run_id]


def test_successful_exit_is_completed_inconclusive(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker)
    job = store.create(_spec())
    sup.tick()
    pid = store.get(job.run_id).worker_pid
    assert pid is not None
    worker.succeed(pid)
    sup.tick()
    done = store.get(job.run_id)
    assert done.status is JobStatus.COMPLETED
    assert done.research_outcome is ResearchOutcome.INCONCLUSIVE


def test_crash_restarts_until_max_then_fails(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, max_recovery=2, heartbeat_timeout_s=60.0)
    job = store.create(_spec())
    sup.tick()
    pid1 = store.get(job.run_id).worker_pid
    worker.crash(pid1)
    sup.tick()
    assert store.get(job.run_id).status is JobStatus.RUNNING
    assert store.get(job.run_id).recovery_attempts == 1
    pid2 = store.get(job.run_id).worker_pid
    worker.crash(pid2)
    sup.tick()
    failed = store.get(job.run_id)
    assert failed.status is JobStatus.FAILED
    assert failed.research_outcome is ResearchOutcome.INCONCLUSIVE
    assert failed.recovery_attempts == 2


def test_replacement_worker_gets_fresh_heartbeat_on_spawn(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, max_recovery=2, heartbeat_timeout_s=60.0)
    job = store.create(_spec())
    sup.tick()
    pid1 = store.get(job.run_id).worker_pid
    assert pid1 is not None

    worker.write_heartbeat_on_spawn = False
    worker.crash(pid1)
    sup.tick()
    replacement = store.get(job.run_id)
    assert replacement.worker_pid is not None
    assert replacement.worker_pid != pid1

    sup.tick()
    still_running = store.get(job.run_id)
    assert still_running.status is JobStatus.RUNNING
    assert still_running.recovery_attempts == 1


def test_cancel_kills_worker(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker)
    job = store.create(_spec())
    sup.tick()
    cancelled = sup.request_cancel(job.run_id)
    assert cancelled.status is JobStatus.CANCELLED
    assert cancelled.research_outcome is ResearchOutcome.INCONCLUSIVE
    assert worker.terminated != []
