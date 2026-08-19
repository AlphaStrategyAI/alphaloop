from __future__ import annotations

import asyncio
import os

import pytest
import yaml

import alphaloop.runtime.worker as worker_module
from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.status import JobStatus, ResearchOutcome, derive_research_outcome
from alphaloop.runtime.checkpoint import load_latest_complete, read_heartbeat
from alphaloop.runtime.worker import (
    ProcessWorker,
    is_worker_cmdline,
    run_worker,
    stopgap_terminal_outcome,
)
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


def test_run_worker_refreshes_heartbeat_while_runner_is_active(monkeypatch, tmp_path):
    run_id = "j_test"
    layout = RunLayout(tmp_path / run_id)
    layout.run_dir.mkdir()
    layout.research_spec.write_text(
        yaml.safe_dump(_spec().to_dict()),
        encoding="utf-8",
    )
    monkeypatch.setattr("alphaloop.runtime.worker.HEARTBEAT_INTERVAL_S", 0.05)

    class SlowRunner:
        async def run(self):
            initial = read_heartbeat(layout)
            assert initial is not None
            await asyncio.sleep(0.2)
            refreshed = read_heartbeat(layout)
            assert refreshed is not None
            assert refreshed["at"] != initial["at"]

    def runner_factory(**kwargs):
        return SlowRunner()

    assert run_worker(run_id, tmp_path, runner_factory=runner_factory) == 0


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

    monkeypatch.setattr(
        "alphaloop.runtime.worker.find_running_worker_pid",
        lambda run_id: None,
    )
    monkeypatch.setattr("alphaloop.runtime.worker.subprocess.Popen", fake_popen)
    worker = ProcessWorker()
    assert worker.spawn("j_test", tmp_path) == 123
    assert calls[0][1:3] == ["-m", "alphaloop.runtime.worker"]
    assert "--run-id" in calls[0]
    assert "--data-dir" in calls[0]
    assert worker.poll(123) is None
    worker.terminate(123)
    assert calls[-1] == "terminated"


def test_process_worker_adopts_existing_matching_run(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "alphaloop.runtime.worker.find_running_worker_pid",
        lambda run_id: 321 if run_id == "j_test" else None,
    )
    monkeypatch.setattr(
        "alphaloop.runtime.worker.subprocess.Popen",
        lambda command: pytest.fail("must not spawn a duplicate worker"),
    )

    assert ProcessWorker().spawn("j_test", tmp_path) == 321


def test_process_worker_rejects_wrong_run_for_tracked_pid(monkeypatch, tmp_path):
    terminated = []

    class FakeProcess:
        pid = 123

        def poll(self):
            return None

        def terminate(self):
            terminated.append(self.pid)

    monkeypatch.setattr(
        "alphaloop.runtime.worker.find_running_worker_pid",
        lambda run_id: None,
    )
    monkeypatch.setattr(
        "alphaloop.runtime.worker.subprocess.Popen",
        lambda command: FakeProcess(),
    )
    worker = ProcessWorker()
    pid = worker.spawn("j_test", tmp_path)

    assert worker.poll(pid, run_id="j_other") == 1
    worker.terminate(pid, run_id="j_other")
    assert terminated == []


def test_process_worker_poll_rejects_unknown_live_pid():
    worker = ProcessWorker()

    assert worker.poll(os.getpid()) not in (None, 0)


def test_process_worker_rejects_worker_for_different_run(monkeypatch):
    cmdline = b"python\0-m\0alphaloop.runtime.worker\0--run-id\0j_other"
    monkeypatch.setattr(
        "alphaloop.runtime.worker.Path.read_bytes",
        lambda path: cmdline,
    )
    signals = []
    monkeypatch.setattr(
        "alphaloop.runtime.worker.os.kill",
        lambda pid, signal: signals.append((pid, signal)),
    )
    worker = ProcessWorker()

    assert worker.poll(456, run_id="j_x") == 1
    worker.terminate(456, run_id="j_x")
    assert signals == []


def test_is_worker_cmdline_accepts_module_entrypoint():
    cmdline = b"python\0-m\0alphaloop.runtime.worker\0--run-id\0x"
    assert is_worker_cmdline(cmdline) is True


def test_is_worker_for_run_accepts_exact_run_id():
    cmdline = b"python\0-m\0alphaloop.runtime.worker\0--run-id\0j_x"
    assert worker_module.is_worker_for_run(cmdline, "j_x") is True


def test_is_worker_for_run_rejects_different_run_id():
    cmdline = b"python\0-m\0alphaloop.runtime.worker\0--run-id\0j_other"
    assert worker_module.is_worker_for_run(cmdline, "j_x") is False


def test_is_worker_cmdline_rejects_exec_string():
    cmdline = b"python\0-c\0import alphaloop.runtime.worker"
    assert is_worker_cmdline(cmdline) is False


def test_is_worker_cmdline_rejects_substring_in_single_argv():
    cmdline = b"evil alphaloop.runtime.worker\0"
    assert is_worker_cmdline(cmdline) is False


def test_process_worker_terminate_ignores_unknown_live_pid(monkeypatch):
    worker = ProcessWorker()
    signals = []
    monkeypatch.setattr(
        "alphaloop.runtime.worker.os.kill",
        lambda pid, signal: signals.append((pid, signal)),
    )

    worker.terminate(os.getpid())

    assert signals == []
