from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Protocol

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.status import JobStatus
from alphaloop.runtime.checkpoint import read_heartbeat, write_heartbeat
from alphaloop.runtime.store import JobRecord, JobStore

MAX_RECOVERY_ATTEMPTS = 3


class WorkerHandle(Protocol):
    def spawn(self, run_id: str, data_dir: Path) -> int: ...

    def poll(self, pid: int, run_id: Optional[str] = None) -> Optional[int]: ...

    def terminate(self, pid: int, run_id: Optional[str] = None) -> None: ...


class Supervisor:
    def __init__(
        self,
        store: JobStore,
        data_dir: Path,
        worker: WorkerHandle,
        *,
        heartbeat_timeout_s: float = 15.0,
        max_recovery: int = MAX_RECOVERY_ATTEMPTS,
    ) -> None:
        self.store = store
        self.data_dir = Path(data_dir)
        self.worker = worker
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self.max_recovery = max_recovery
        self.lifecycle_lock = threading.Lock()

    def tick(self) -> None:
        with self.lifecycle_lock:
            for job in self.store.list_jobs():
                if job.status is JobStatus.QUEUED:
                    self._spawn(job.run_id)
                elif job.status is JobStatus.RUNNING:
                    self._monitor(job)

    def request_cancel(self, run_id: str) -> JobRecord:
        with self.lifecycle_lock:
            job = self.store.get(run_id)
            if job.status in (
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            ):
                return job
            if job.worker_pid is not None:
                self.worker.terminate(job.worker_pid, run_id)
            return self.store.update_status(run_id, JobStatus.CANCELLED)

    def _spawn(self, run_id: str) -> JobRecord:
        pid = self.worker.spawn(run_id, self.data_dir)
        at = datetime.now(timezone.utc).isoformat()
        write_heartbeat(RunLayout(self.data_dir / run_id), pid=pid, at=at)
        self.store.update_status(run_id, JobStatus.RUNNING, worker_pid=pid)
        return self.store.set_heartbeat(run_id, pid=pid, at=at)

    def _monitor(self, job: JobRecord) -> None:
        if job.worker_pid is None:
            self._recover(job, worker_running=False)
            return

        code = self.worker.poll(job.worker_pid, job.run_id)
        if code == 0:
            self.store.update_status(job.run_id, JobStatus.COMPLETED)
            return
        if code is not None:
            self._recover(job, worker_running=False)
            return
        if self._heartbeat_is_stale(job):
            self._recover(job, worker_running=True)

    def _recover(self, job: JobRecord, *, worker_running: bool) -> None:
        if worker_running and job.worker_pid is not None:
            self.worker.terminate(job.worker_pid, job.run_id)
        if job.recovery_attempts >= self.max_recovery:
            self._mark_recovery_exhausted(job.run_id)
            return

        attempted = self.store.increment_recovery(job.run_id)
        if attempted.recovery_attempts >= self.max_recovery:
            self._mark_recovery_exhausted(job.run_id)
            return
        self._spawn(job.run_id)

    def _mark_recovery_exhausted(self, run_id: str) -> None:
        self.store.update_status(
            run_id,
            JobStatus.FAILED,
            error="worker recovery exhausted",
        )

    def _heartbeat_is_stale(self, job: JobRecord) -> bool:
        heartbeat = read_heartbeat(RunLayout(self.data_dir / job.run_id))
        file_at = (
            self._heartbeat_at(heartbeat)
            if heartbeat is not None and heartbeat.get("pid") == job.worker_pid
            else None
        )
        at = file_at or job.heartbeat_at
        if at is None:
            return True
        try:
            heartbeat_time = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError:
            return True
        if heartbeat_time.tzinfo is None:
            heartbeat_time = heartbeat_time.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - heartbeat_time.astimezone(timezone.utc)
        return age > timedelta(seconds=self.heartbeat_timeout_s)

    @staticmethod
    def _heartbeat_at(heartbeat: Optional[dict]) -> Optional[str]:
        if heartbeat is None:
            return None
        at = heartbeat.get("at")
        return at if isinstance(at, str) else None
