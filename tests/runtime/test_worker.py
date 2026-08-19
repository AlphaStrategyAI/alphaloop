from __future__ import annotations

import asyncio
import json
import os

import pandas as pd
import pytest
import yaml

import alphaloop.runtime.worker as worker_module
from alphaloop.contracts.artifacts import DatasetRef, RunLayout
from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.contracts.status import JobStatus, ResearchOutcome, derive_research_outcome
from alphaloop.runtime.checkpoint import (
    Checkpoint,
    load_latest_complete,
    read_heartbeat,
    write_checkpoint,
)
from alphaloop.runtime.worker import (
    ProcessWorker,
    is_worker_cmdline,
    run_worker,
    stopgap_terminal_outcome,
)
from tests.runtime.test_supervisor import _spec


def _write_prices_parquet(path, prices: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(prices).to_parquet(path)


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


def test_run_worker_passes_clock_and_cost_budget(monkeypatch, tmp_path):
    captured = {}

    def fake_run_protocol(spec, layout, **kwargs):
        captured["kwargs"] = kwargs
        captured["spec"] = spec
        return None

    monkeypatch.setattr("alphaloop.protocol.loop.run_protocol", fake_run_protocol)
    run_id = "j_clock"
    layout = RunLayout(tmp_path / run_id)
    layout.run_dir.mkdir()
    spec = _spec()
    layout.research_spec.write_text(
        yaml.safe_dump(spec.to_dict()),
        encoding="utf-8",
    )
    idx = pd.bdate_range("2018-01-01", periods=30)
    _write_prices_parquet(
        layout.run_dir / "prices.parquet",
        {
            "AAPL": pd.Series(range(30), index=idx, dtype=float),
            "MSFT": pd.Series(range(30), index=idx, dtype=float),
            "SPY": pd.Series(range(30), index=idx, dtype=float),
        },
    )
    assert run_worker(run_id, tmp_path) == 0
    assert callable(captured["kwargs"]["clock"])
    assert captured["kwargs"]["remaining_cost_usd"] == spec.cost_budget_usd
    first = captured["kwargs"]["clock"]()
    second = captured["kwargs"]["clock"]()
    assert second >= first


def test_run_worker_default_path_writes_protocol_artifacts(tmp_path):
    run_id = "j_protocol"
    layout = RunLayout(tmp_path / run_id)
    layout.run_dir.mkdir()
    layout.research_spec.write_text(
        yaml.safe_dump(_spec().to_dict()),
        encoding="utf-8",
    )
    idx = pd.bdate_range("2018-01-01", periods=30)
    _write_prices_parquet(
        layout.run_dir / "prices.parquet",
        {
            "AAPL": pd.Series(range(30), index=idx, dtype=float),
            "MSFT": pd.Series(range(30), index=idx, dtype=float),
            "SPY": pd.Series(range(30), index=idx, dtype=float),
        },
    )
    assert run_worker(run_id, tmp_path) == 0
    rec = json.loads(layout.recommendations.read_text(encoding="utf-8"))
    assert rec["queued_hypotheses"] == []
    assert layout.trial_ledger.exists()


def test_run_worker_without_snapshot_does_not_synthesize(tmp_path):
    run_id = "j_nosnap"
    layout = RunLayout(tmp_path / run_id)
    layout.run_dir.mkdir()
    layout.research_spec.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    assert run_worker(run_id, tmp_path) == 0
    assert not (layout.evidence / "gates.json").exists()
    assert not layout.trial_ledger.exists() or layout.trial_ledger.read_text() == ""


def test_run_worker_rejects_hash_mismatch(tmp_path):
    idx = pd.bdate_range("2018-01-01", periods=30)
    frame = pd.DataFrame({"AAPL": range(30), "MSFT": range(30), "SPY": range(30)}, index=idx)
    blob_path = tmp_path / "datasets" / "ds_bad" / "prices.parquet"
    _write_prices_parquet(blob_path, {c: frame[c] for c in frame.columns})
    spec = new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr",),
        seed=7,
        time_budget_s=60,
        cost_budget_usd=1.0,
        dataset=DatasetRef(dataset_id="ds_bad", sha256="0" * 64),
    )
    run_id = "j_mismatch"
    layout = RunLayout(tmp_path / run_id)
    layout.run_dir.mkdir()
    layout.research_spec.write_text(yaml.safe_dump(spec.to_dict()), encoding="utf-8")
    assert run_worker(run_id, tmp_path) == 0
    assert not (layout.evidence / "gates.json").exists()


def test_run_worker_resumes_from_checkpoint_ids(monkeypatch, tmp_path):
    captured = {}

    def fake_run_protocol(spec, layout, **kwargs):
        captured["completed"] = kwargs.get("completed_trial_ids")
        captured["on_trial"] = kwargs.get("on_trial")
        return None

    monkeypatch.setattr("alphaloop.protocol.loop.run_protocol", fake_run_protocol)
    run_id = "j_resume"
    layout = RunLayout(tmp_path / run_id)
    layout.run_dir.mkdir()
    layout.research_spec.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    idx = pd.bdate_range("2018-01-01", periods=30)
    _write_prices_parquet(
        layout.run_dir / "prices.parquet",
        {"AAPL": pd.Series(range(30), index=idx, dtype=float),
         "MSFT": pd.Series(range(30), index=idx, dtype=float),
         "SPY": pd.Series(range(30), index=idx, dtype=float)},
    )
    write_checkpoint(
        layout,
        Checkpoint(
            seq=3,
            complete=True,
            payload={"phase": "protocol", "completed_trial_ids": ["c_already"]},
        ),
    )
    assert run_worker(run_id, tmp_path) == 0
    assert captured["completed"] == ["c_already"] or captured["completed"] == ("c_already",)
    captured["on_trial"]({"trial_id": "c_new", "completed_trial_ids": ("c_already", "c_new"), "n_trials": 2})
    latest = load_latest_complete(layout)
    assert latest is not None
    assert latest.seq == 4
    assert latest.payload["completed_trial_ids"][-1] == "c_new"


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
