from __future__ import annotations

from pathlib import Path
from typing import Any

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.research_spec import ResearchSpec
from alphaloop.contracts.status import JobStatus
from alphaloop.protocol.search import method_parameter_grid
from alphaloop.runtime.asb_export import export_found_asb
from alphaloop.runtime.dataset_cache import cache_dataset_bytes
from alphaloop.runtime.example_dataset import ensure_example_dataset
from alphaloop.runtime.morning import format_export_handoff, morning_view
from alphaloop.runtime.preflight import preflight
from alphaloop.runtime.store import JobStore
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
        ensure_example_dataset(self.data_dir)

    def create_run(self, spec: ResearchSpec) -> dict[str, Any]:
        result = preflight(spec, self.data_dir)
        if not result.ok:
            raise PreflightRejected(result.errors)
        job = self.store.create(spec)
        payload = morning_view(job, self.data_dir)
        payload["host_constraint"] = result.host_constraint
        return payload

    def preview_run(self, spec: ResearchSpec) -> dict[str, Any]:
        result = preflight(spec, self.data_dir)
        grid = list(method_parameter_grid(spec.hypothesis.signal_mechanism))
        return {
            "ok": result.ok,
            "errors": list(result.errors),
            "host_constraint": result.host_constraint,
            "spec_id": spec.spec_id,
            "seed": spec.seed,
            "statement": spec.hypothesis.statement,
            "signal_mechanism": spec.hypothesis.signal_mechanism,
            "hard_gates": list(spec.success_criteria.hard_gates),
            "method_parameter_grid": grid,
            "planned_n_trials": len(grid),
            "time_budget_s": spec.time_budget_s,
            "cost_budget_usd": spec.cost_budget_usd,
        }

    def list_jobs(self) -> dict[str, Any]:
        return {
            "jobs": [morning_view(job, self.data_dir) for job in self.store.list_jobs()]
        }

    def get_run(self, run_id: str) -> dict[str, Any]:
        return morning_view(self.store.get(run_id), self.data_dir)

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        return morning_view(self.supervisor.request_cancel(run_id), self.data_dir)

    def resume_run(self, run_id: str) -> dict[str, Any]:
        with self.supervisor.lifecycle_lock:
            job = self.store.get(run_id)
            if job.status in (JobStatus.CANCELLED, JobStatus.COMPLETED):
                raise ValueError(f"cannot resume {job.status.value} job")
            pid = job.worker_pid
            if job.status is JobStatus.RUNNING and pid is not None:
                self.supervisor.worker.terminate(pid, run_id)
            return morning_view(
                self.store.requeue_unless_terminal(run_id, expected_pid=pid),
                self.data_dir,
            )

    def replay_run(self, run_id: str) -> dict[str, Any]:
        from alphaloop.runtime.replay import rewrite_sealed_report

        self.store.get(run_id)
        rewrite_sealed_report(self.data_dir, run_id)
        return morning_view(self.store.get(run_id), self.data_dir)

    def export_run(self, run_id: str, candidate_id: str) -> dict[str, Any]:
        dest = (
            RunLayout(self.data_dir / run_id).run_dir
            / "exports"
            / f"{Path(candidate_id).name}.asb"
        )
        export_found_asb(
            store=self.store,
            data_dir=self.data_dir,
            run_id=run_id,
            candidate_id=candidate_id,
            output=dest,
        )
        view = morning_view(self.store.get(run_id), self.data_dir)
        view["exported_path"] = str(dest)
        view["exported_candidate_id"] = candidate_id
        view["export_handoff"] = format_export_handoff(
            candidate_id=candidate_id,
            exported_path=str(dest),
        )
        return view

    def put_dataset(self, blob: bytes) -> dict[str, str]:
        ref = cache_dataset_bytes(self.data_dir, blob)
        return {"dataset_id": ref.dataset_id, "sha256": ref.sha256}
