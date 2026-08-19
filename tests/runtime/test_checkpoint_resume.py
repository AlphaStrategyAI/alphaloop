from __future__ import annotations

import json

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import GateResult, HardGateName, IncompleteEvidenceError, evaluate_hard_gates
from alphaloop.protocol.loop import run_protocol
from alphaloop.runtime.checkpoint import Checkpoint, load_latest_complete, write_checkpoint
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
