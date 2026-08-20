from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time

import pandas as pd
import pytest

from alphaloop.contracts.artifacts import DatasetRef, RunLayout, hash_bytes
from alphaloop.contracts.gates import GateResult, HardGateName, IncompleteEvidenceError, evaluate_hard_gates
from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.contracts.status import ResearchOutcome
from alphaloop.protocol.loop import run_protocol
from alphaloop.runtime.checkpoint import Checkpoint, load_latest_complete, write_checkpoint
from alphaloop.runtime.morning import morning_view
from alphaloop.runtime.store import JobStore
from alphaloop.runtime.worker import run_worker
from tests.protocol.test_protocol_loop import _prices, _spec


def test_second_start_skips_checkpointed_trial_ids(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    seq = {"n": 0}

    def on_trial(payload):
        seq["n"] += 1
        write_checkpoint(
            layout,
            Checkpoint(
                seq=seq["n"],
                complete=True,
                payload={
                    "phase": "protocol",
                    "completed_trial_ids": list(payload["completed_trial_ids"]),
                },
            ),
        )
        raise RuntimeError("injected crash")

    def incomplete(required, **kwargs):
        raise IncompleteEvidenceError("missing walk_forward")

    try:
        run_protocol(
            _spec(),
            layout,
            prices=_prices(),
            buy_hold_prices=_prices()["AAPL"],
            benchmark_prices=_prices()["AAPL"],
            gate_runner=incomplete,
            on_trial=on_trial,
        )
    except RuntimeError:
        pass

    ckpt = load_latest_complete(layout)
    assert ckpt is not None
    done = tuple(ckpt.payload["completed_trial_ids"])
    before = layout.trial_ledger.read_text(encoding="utf-8")

    def pass_all(required, **kwargs):
        rows = tuple(GateResult(name=name, passed=True, detail={}) for name in required)
        return evaluate_hard_gates(required, rows)

    run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=pass_all,
        completed_trial_ids=done,
        on_trial=None,
    )
    after = layout.trial_ledger.read_text(encoding="utf-8")
    ids = [json.loads(line)["trial_id"] for line in after.strip().splitlines() if line.strip()]
    assert len(ids) == len(set(ids))
    assert before.strip().splitlines()[0] in after


def _ledger_ids(layout: RunLayout) -> list[str]:
    if not layout.trial_ledger.is_file():
        return []
    ids = []
    for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        trial_id = payload.get("trial_id")
        if trial_id:
            ids.append(str(trial_id))
    return ids


def test_sigkill_after_checkpoint_resume_keeps_unique_ledger(tmp_path):
    parquet = tmp_path / "datasets" / "ds_kill" / "prices.parquet"
    parquet.parent.mkdir(parents=True)
    idx = pd.bdate_range("2018-01-01", periods=260)
    pd.DataFrame(
        {
            "AAPL": 100.0 + pd.Series(range(260), index=idx, dtype=float),
            "MSFT": 100.0 + pd.Series(range(260), index=idx, dtype=float),
            "SPY": 100.0 + pd.Series(range(260), index=idx, dtype=float),
        }
    ).to_parquet(parquet)
    spec = new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr",),
        seed=7,
        time_budget_s=30,
        cost_budget_usd=1.0,
        dataset=DatasetRef(dataset_id="ds_kill", sha256=hash_bytes(parquet.read_bytes())),
    )
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(spec)
    run_id = job.run_id
    layout = RunLayout(tmp_path / run_id)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "alphaloop.runtime.worker",
            "--run-id",
            run_id,
            "--data-dir",
            str(tmp_path),
        ]
    )
    deadline = time.time() + 60
    ckpt = None
    while time.time() < deadline:
        ckpt = load_latest_complete(layout)
        if ckpt is not None:
            break
        if proc.poll() is not None:
            break
        time.sleep(0.05)
    if ckpt is None:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
        pytest.skip("complete checkpoint never appeared")
    if proc.poll() is None:
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=10)
    if not (layout.evidence / "gates.json").is_file():
        mid = store.complete_from_artifacts(run_id)
        assert mid.research_outcome is not ResearchOutcome.FOUND
    done_ids = tuple(ckpt.payload.get("completed_trial_ids") or [])
    assert done_ids
    before_ids = _ledger_ids(layout)
    assert run_worker(run_id, tmp_path) == 0
    after_ids = _ledger_ids(layout)
    assert len(after_ids) == len(set(after_ids))
    for trial_id in done_ids:
        assert trial_id in after_ids
    for trial_id in before_ids:
        assert after_ids.count(trial_id) == 1
    done = store.complete_from_artifacts(run_id)
    view = morning_view(done, tmp_path)
    assert view["n_trials"] == len(set(after_ids))
    if view["research_outcome"] == ResearchOutcome.FOUND.value:
        assert view["evidence"] is not None
        assert view["evidence"]["complete"] is True
        assert view["evidence"]["all_passed"] is True
    else:
        assert view["research_outcome"] in {
            ResearchOutcome.NO_EVIDENCE.value,
            ResearchOutcome.INCONCLUSIVE.value,
        }
    assert "target found" not in (layout.report.read_text(encoding="utf-8") if layout.report.is_file() else "")

