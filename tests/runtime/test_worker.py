from __future__ import annotations

import os

import yaml

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.status import JobStatus, ResearchOutcome, derive_research_outcome
from alphaloop.runtime.checkpoint import load_latest_complete, read_heartbeat
from alphaloop.runtime.worker import ProcessWorker, run_worker, stopgap_terminal_outcome
from tests.runtime.test_supervisor import _spec


def test_stopgap_never_claims_found():
    outcome = stopgap_terminal_outcome()
    assert outcome is ResearchOutcome.INCONCLUSIVE
    assert outcome is derive_research_outcome(JobStatus.COMPLETED, False, False)
    assert outcome is not ResearchOutcome.FOUND


def test_stopgap_does_not_use_termination_letter():
    assert stopgap_terminal_outcome() != "A"
    assert getattr(stopgap_terminal_outcome(), "value", None) != "target found"


def test_run_worker_checkpoints_and_heartbeats_before_dry_run(tmp_path):
    run_id = "j_test"
    layout = RunLayout(tmp_path / run_id)
    layout.run_dir.mkdir()
    layout.research_spec.write_text(
        yaml.safe_dump(_spec().to_dict()),
        encoding="utf-8",
    )
    factory_kwargs = {}

    class FakeRunner:
        async def run(self):
            checkpoint = load_latest_complete(layout)
            heartbeat = read_heartbeat(layout)
            assert checkpoint is not None
            assert checkpoint.seq == 1
            assert checkpoint.complete is True
            assert heartbeat is not None
            assert heartbeat["pid"] == os.getpid()
            return type("Summary", (), {"termination_reason": "A"})()

    def runner_factory(**kwargs):
        factory_kwargs.update(kwargs)
        return FakeRunner()

    assert run_worker(run_id, tmp_path, runner_factory=runner_factory) == 0
    assert factory_kwargs["run_id"] == run_id
    assert factory_kwargs["dry_run"] is True


def test_process_worker_uses_module_entrypoint(monkeypatch, tmp_path):
    calls = []

    class FakeProcess:
        pid = 123

        def poll(self):
            return None

        def terminate(self):
            calls.append("terminated")

    def fake_popen(command):
        calls.append(command)
        return FakeProcess()

    monkeypatch.setattr("alphaloop.runtime.worker.subprocess.Popen", fake_popen)
    worker = ProcessWorker()
    assert worker.spawn("j_test", tmp_path) == 123
    assert calls[0][1:3] == ["-m", "alphaloop.runtime.worker"]
    assert "--run-id" in calls[0]
    assert "--data-dir" in calls[0]
    assert worker.poll(123) is None
    worker.terminate(123)
    assert calls[-1] == "terminated"
