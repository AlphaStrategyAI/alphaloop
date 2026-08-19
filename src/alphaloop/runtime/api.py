from __future__ import annotations

from pathlib import Path
from typing import Any

from alphaloop.contracts.research_spec import ResearchSpec
from alphaloop.contracts.status import JobStatus
from alphaloop.runtime.preflight import preflight
from alphaloop.runtime.store import JobRecord, JobStore
from alphaloop.runtime.supervisor import Supervisor


class PreflightRejected(ValueError):  # noqa: N818 - public API name
    pass


class JobAPI:
    def __init__(
        self,
        store: JobStore,
        supervisor: Supervisor,
        data_dir: Path,
    ) -> None:
        self.store = store
        self.supervisor = supervisor
        self.data_dir = Path(data_dir)

    def create_run(self, spec: ResearchSpec) -> dict[str, Any]:
        result = preflight(spec, self.data_dir)
        if not result.ok:
            raise PreflightRejected(result.errors)
        job = self.store.create(spec)
        payload = self._job_dict(job)
        payload["host_constraint"] = result.host_constraint
        return payload

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._job_dict(self.store.get(run_id))

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        return self._job_dict(self.supervisor.request_cancel(run_id))

    def resume_run(self, run_id: str) -> dict[str, Any]:
        job = self.store.get(run_id)
        if job.status in (JobStatus.CANCELLED, JobStatus.COMPLETED):
            raise ValueError(f"cannot resume {job.status.value} job")
        return self._job_dict(
            self.store.update_status(run_id, JobStatus.QUEUED, error=None)
        )

    @staticmethod
    def _job_dict(job: JobRecord) -> dict[str, Any]:
        return {
            "run_id": job.run_id,
            "status": job.status.value,
            "research_outcome": job.research_outcome.value,
            "spec_id": job.spec.spec_id,
            "error": job.error,
            "recovery_attempts": job.recovery_attempts,
        }
