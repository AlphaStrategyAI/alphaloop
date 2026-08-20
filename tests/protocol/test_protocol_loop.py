from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import (
    GateResult,
    HardGateName,
    IncompleteEvidenceError,
    evidence_from_dict,
    evaluate_hard_gates,
)
from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.contracts.status import JobStatus, ResearchOutcome
from alphaloop.protocol.loop import run_protocol
from alphaloop.protocol.returns import compute_strategy_returns


def _spec(**overrides):
    payload = dict(
        statement="12-1 momentum works",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "vs_buy_hold"),
        seed=7,
        time_budget_s=60,
        cost_budget_usd=1.0,
    )
    payload.update(overrides)
    return new_research_spec(**payload)


def _prices():
    idx = pd.bdate_range("2018-01-01", periods=300)
    series = pd.Series([100.0 + i for i in range(300)], index=idx, dtype=float)
    return {"AAPL": series, "MSFT": series}


def _all_pass(required, **kwargs):
    rows = tuple(GateResult(name=name, passed=True, detail={}) for name in required)
    return evaluate_hard_gates(required, rows)


def _one_fail(required, **kwargs):
    rows = []
    for i, name in enumerate(required):
        rows.append(GateResult(name=name, passed=i != 0, detail={}))
    return evaluate_hard_gates(required, tuple(rows))


def _incomplete(required, **kwargs):
    raise IncompleteEvidenceError("missing walk_forward")


def _cid(kind, parameters):
    encoded = json.dumps({"kind": kind, "parameters": dict(parameters)}, sort_keys=True).encode()
    return "c_" + hashlib.sha256(encoded).hexdigest()[:16]


def test_protocol_found_from_passing_gates(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_all_pass,
    )
    assert result.job_status is JobStatus.COMPLETED
    assert result.research_outcome is ResearchOutcome.FOUND
    assert result.candidate_id
    evidence = evidence_from_dict(json.loads((layout.evidence / "gates.json").read_text()))
    assert evidence.all_passed is True
    ledger = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(ledger) == 1
    rec = json.loads(layout.recommendations.read_text(encoding="utf-8"))
    assert rec["queued_hypotheses"] == []


def test_found_stops_after_first_passing_trial(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    calls = {"n": 0}

    def runner(required, **kwargs):
        calls["n"] += 1
        return _all_pass(required, **kwargs)

    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    assert result.research_outcome is ResearchOutcome.FOUND
    assert calls["n"] == 1
    ledger = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(ledger) == 1


def test_complete_fail_walks_the_frozen_parameter_grid(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    calls = {"n": 0}

    def runner(required, **kwargs):
        calls["n"] += 1
        return _one_fail(required, **kwargs)

    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    assert result.research_outcome is ResearchOutcome.NO_EVIDENCE
    assert calls["n"] == 3
    ledger = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(ledger) == 3
    trial_files = list((layout.evidence / "trials").glob("*.json"))
    assert len(trial_files) == 3
    rec = json.loads(layout.recommendations.read_text(encoding="utf-8"))
    assert rec["queued_hypotheses"][0]["signal_mechanism"] == "rsi"
    assert rec["queued_hypotheses"][0]["queued_reason"] == "economic_change_queued"
    assert "not a claim of alpha" in rec["queued_hypotheses"][0]["statement"].lower()


def test_later_frozen_grid_point_can_found(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    calls = {"n": 0}

    def runner(required, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _one_fail(required, **kwargs)
        return _all_pass(required, **kwargs)

    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    assert result.research_outcome is ResearchOutcome.FOUND
    assert calls["n"] == 2


def test_frozen_grid_does_not_call_revision_proposer(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    calls = {"n": 0}
    proposed = {"n": 0}

    def runner(required, **kwargs):
        calls["n"] += 1
        return _one_fail(required, **kwargs)

    def proposer(spec, doc):
        proposed["n"] += 1
        return {"signal_mechanism": "macd"}

    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
        revision_proposer=proposer,
    )
    rec = json.loads(layout.recommendations.read_text(encoding="utf-8"))
    assert proposed["n"] == 0
    assert all(item.get("signal_mechanism") != "macd" for item in rec["queued_hypotheses"])
    assert result.research_outcome is ResearchOutcome.NO_EVIDENCE
    assert calls["n"] == 3


class _IncompleteThenPass:
    def __init__(self):
        self.calls = []

    def __call__(self, required, **kwargs):
        self.calls.append(kwargs["n_trials"])
        if len(self.calls) == 1:
            raise IncompleteEvidenceError("missing walk_forward")
        return _all_pass(required, **kwargs)


def test_method_repair_retries_and_counts_trials(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    runner = _IncompleteThenPass()
    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    assert result.research_outcome is ResearchOutcome.FOUND
    assert runner.calls == [1, 2]
    ledger = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(ledger) == 2
    assert json.loads(ledger[0])["revision"] == "none"
    assert json.loads(ledger[1])["revision"] == "method"
    assert json.loads(ledger[1])["parameters"] == {"lookback": 126, "skip": 21}
    evidence = evidence_from_dict(json.loads((layout.evidence / "gates.json").read_text()))
    assert evidence.all_passed is True


def test_found_after_trial_when_clock_exhausts_during_gates(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    ticks = {"n": 0}

    def clock():
        ticks["n"] += 1
        if ticks["n"] == 1:
            return 0.0
        return 1000.0

    result = run_protocol(
        _spec(time_budget_s=10),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_all_pass,
        clock=clock,
    )
    assert result.research_outcome is ResearchOutcome.FOUND
    assert result.job_status is JobStatus.COMPLETED


def test_budget_exhaustion_after_incomplete_is_inconclusive(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    ticks = {"n": 0}

    def clock():
        ticks["n"] += 1
        return 0 if ticks["n"] == 1 else 1000

    result = run_protocol(
        _spec(time_budget_s=10),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_incomplete,
        clock=clock,
    )
    assert result.research_outcome is ResearchOutcome.INCONCLUSIVE
    assert not (layout.evidence / "gates.json").exists()


def test_protocol_no_evidence_from_failed_gate(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_one_fail,
    )
    assert result.research_outcome is ResearchOutcome.NO_EVIDENCE
    assert result.job_status is JobStatus.COMPLETED


def test_protocol_inconclusive_without_complete_gates(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_incomplete,
    )
    assert result.research_outcome is ResearchOutcome.INCONCLUSIVE
    assert not (layout.evidence / "gates.json").exists()


def test_unknown_kind_is_inconclusive(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    result = run_protocol(
        _spec(signal_mechanism="NotAClass"),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_all_pass,
    )
    assert result.research_outcome is ResearchOutcome.INCONCLUSIVE
    assert result.candidate_id is None


def test_protocol_does_not_mutate_frozen_hypothesis(tmp_path):
    spec = _spec()
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    run_protocol(
        spec,
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_all_pass,
    )
    assert spec.hypothesis.signal_mechanism == "momentum_12_1"


def test_gate_runner_receives_lagged_weight_returns_not_raw_prices(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    captured = {}

    def runner(required, **kwargs):
        captured["strategy_returns"] = kwargs["strategy_returns"]
        captured["strategy_fn"] = kwargs["strategy_fn"]
        return _all_pass(required, **kwargs)

    prices = _prices()
    run_protocol(
        _spec(),
        layout,
        prices=prices,
        buy_hold_prices=prices["AAPL"],
        benchmark_prices=prices["AAPL"],
        gate_runner=runner,
    )
    raw = prices["AAPL"].pct_change().fillna(0.0)
    assert "strategy_returns" in captured
    assert not captured["strategy_returns"].equals(raw)
    weights = captured["strategy_fn"](prices["AAPL"])
    expected = compute_strategy_returns(prices["AAPL"], weights, cost_bps=5.0)
    pd.testing.assert_series_equal(
        captured["strategy_returns"],
        expected,
        check_names=False,
    )


def test_economic_proposal_is_queued_and_not_executed(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    calls = {"n": 0}

    def runner(required, **kwargs):
        calls["n"] += 1
        raise IncompleteEvidenceError("missing walk_forward")

    def proposer(spec, doc):
        return {"signal_mechanism": "rsi"}

    spec = _spec()
    result = run_protocol(
        spec,
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
        revision_proposer=proposer,
    )
    assert spec.hypothesis.signal_mechanism == "momentum_12_1"
    rec = json.loads(layout.recommendations.read_text(encoding="utf-8"))
    assert rec["queued_hypotheses"][0]["signal_mechanism"] == "rsi"
    assert result.research_outcome is ResearchOutcome.INCONCLUSIVE
    assert calls["n"] == 1


def test_n_trials_matches_unique_ledger_ids(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    seen = []

    def runner(required, **kwargs):
        seen.append(kwargs["n_trials"])
        if len(seen) == 1:
            raise IncompleteEvidenceError("missing walk_forward")
        return _all_pass(required, **kwargs)

    run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    lines = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    ids = [json.loads(line)["trial_id"] for line in lines]
    assert seen[-1] == len(set(ids)) == len(ids)
    assert seen == [1, 2]


def test_n_trials_counts_existing_ledger_rows(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    layout.trial_ledger.write_text(
        json.dumps({"trial_id": "c_prior", "kind": "momentum_12_1", "parameters": {}})
        + "\n",
        encoding="utf-8",
    )
    seen = []

    def runner(required, **kwargs):
        seen.append(kwargs["n_trials"])
        return _all_pass(required, **kwargs)

    run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
        completed_trial_ids=(),
    )
    assert seen[0] == 2


def test_completed_trial_ids_are_skipped(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    first_id = _cid("momentum_12_1", {})
    calls = {"n": 0}

    def runner(required, **kwargs):
        calls["n"] += 1
        return _incomplete(required, **kwargs)

    run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
        completed_trial_ids=(first_id,),
    )
    ledger = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    assert calls["n"] >= 1
    assert json.loads(ledger[0])["trial_id"] != first_id


def test_existing_recommendations_are_not_truncated(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    layout.recommendations.write_text(
        json.dumps({"queued_hypotheses": [{"statement": "keep me"}]}) + "\n",
        encoding="utf-8",
    )
    run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_all_pass,
    )
    rec = json.loads(layout.recommendations.read_text(encoding="utf-8"))
    assert rec["queued_hypotheses"][0]["statement"] == "keep me"


def test_retry_does_not_duplicate_ledger_row(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    first_id = _cid("momentum_12_1", {})
    layout.trial_ledger.write_text(
        json.dumps({"trial_id": first_id, "kind": "momentum_12_1", "parameters": {}})
        + "\n",
        encoding="utf-8",
    )
    run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_all_pass,
        completed_trial_ids=(),
    )
    lines = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    ids = [json.loads(line)["trial_id"] for line in lines]
    assert ids.count(first_id) == 1


def test_torn_trailing_ledger_line_does_not_crash_resume(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    first_id = _cid("momentum_12_1", {})
    layout.trial_ledger.write_text(
        json.dumps({"trial_id": first_id, "kind": "momentum_12_1", "parameters": {}})
        + "\n{\"trial_id\": \"c_partial\"",
        encoding="utf-8",
    )
    seen = []

    def runner(required, **kwargs):
        seen.append(kwargs["n_trials"])
        return _incomplete(required, **kwargs)

    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
        completed_trial_ids=(),
    )
    assert result.research_outcome is not ResearchOutcome.FOUND
    assert seen
    assert seen[0] == 1
    parsed = []
    for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("trial_id"):
            parsed.append(row["trial_id"])
    assert first_id in parsed
    assert parsed.count(first_id) == 1
    assert "c_partial" not in parsed


def test_complete_evidence_is_on_disk_before_on_trial_returns(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    seen = {}

    def on_trial(payload):
        gates = layout.evidence / "gates.json"
        seen["exists"] = gates.is_file()
        if gates.is_file():
            evidence = evidence_from_dict(json.loads(gates.read_text(encoding="utf-8")))
            seen["complete"] = evidence.complete
            seen["all_passed"] = evidence.all_passed

    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_all_pass,
        on_trial=on_trial,
    )
    assert seen["exists"] is True
    assert seen["complete"] is True
    assert seen["all_passed"] is True
    assert result.research_outcome is ResearchOutcome.FOUND


def test_incomplete_evidence_does_not_invent_gates_before_on_trial(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    seen = {}

    def on_trial(payload):
        seen["exists"] = (layout.evidence / "gates.json").is_file()

    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_incomplete,
        on_trial=on_trial,
    )
    assert seen["exists"] is False
    assert result.research_outcome is ResearchOutcome.INCONCLUSIVE
    assert not (layout.evidence / "gates.json").exists()


def test_bollinger_protocol_walks_three_method_trials(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    seen: list[int] = []

    def runner(required, **kwargs):
        seen.append(kwargs["n_trials"])
        if len(seen) < 3:
            raise IncompleteEvidenceError("missing walk_forward")
        return _all_pass(required, **kwargs)

    result = run_protocol(
        _spec(signal_mechanism="bollinger_zscore"),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    ids = [
        json.loads(line)["trial_id"]
        for line in layout.trial_ledger.read_text().splitlines()
        if line.strip()
    ]
    assert len(set(ids)) == 3
    assert seen == [1, 2, 3]
    assert result.research_outcome is ResearchOutcome.FOUND


def test_ohlr_protocol_walks_three_method_trials(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    seen: list[int] = []

    def runner(required, **kwargs):
        seen.append(kwargs["n_trials"])
        if len(seen) < 3:
            raise IncompleteEvidenceError("missing walk_forward")
        return _all_pass(required, **kwargs)

    result = run_protocol(
        _spec(signal_mechanism="ohlr_4_pct"),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    ids = [
        json.loads(line)["trial_id"]
        for line in layout.trial_ledger.read_text().splitlines()
        if line.strip()
    ]
    assert len(set(ids)) == 3
    assert seen == [1, 2, 3]
    assert result.research_outcome is ResearchOutcome.FOUND


def test_pairs_protocol_walks_three_method_trials(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    seen: list[int] = []

    def runner(required, **kwargs):
        seen.append(kwargs["n_trials"])
        if len(seen) < 3:
            raise IncompleteEvidenceError("missing walk_forward")
        return _all_pass(required, **kwargs)

    result = run_protocol(
        _spec(signal_mechanism="pairs_spread"),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    ids = [
        json.loads(line)["trial_id"]
        for line in layout.trial_ledger.read_text().splitlines()
        if line.strip()
    ]
    assert len(set(ids)) == 3
    assert seen == [1, 2, 3]
    assert result.research_outcome is ResearchOutcome.FOUND


def test_atr_protocol_walks_three_method_trials(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    seen: list[int] = []

    def runner(required, **kwargs):
        seen.append(kwargs["n_trials"])
        if len(seen) < 3:
            raise IncompleteEvidenceError("missing walk_forward")
        return _all_pass(required, **kwargs)

    result = run_protocol(
        _spec(signal_mechanism="atr_breakout"),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    ids = [
        json.loads(line)["trial_id"]
        for line in layout.trial_ledger.read_text().splitlines()
        if line.strip()
    ]
    assert len(set(ids)) == 3
    assert seen == [1, 2, 3]
    assert result.research_outcome is ResearchOutcome.FOUND


def test_pbo_failure_blocks_found_after_method_repair(tmp_path, monkeypatch):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    runner = _IncompleteThenPass()

    def fake_pbo(returns, **kwargs):
        from alphaloop.diagnostic.pbo import PBOResult

        assert len(returns) >= 2
        return PBOResult(
            evaluated=True,
            pbo=0.8,
            passes=False,
            n_strategies=len(returns),
            n_paths=20,
            n_groups=6,
        )

    monkeypatch.setattr(
        "alphaloop.protocol.loop.probability_of_backtest_overfitting",
        fake_pbo,
    )
    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    assert result.research_outcome is ResearchOutcome.NO_EVIDENCE
    assert runner.calls == [1, 2]
    evidence = evidence_from_dict(json.loads((layout.evidence / "gates.json").read_text()))
    assert evidence.all_passed is False
    dsr = next(row for row in evidence.results if row.name is HardGateName.DSR)
    assert dsr.detail["pbo_passes"] is False
    assert dsr.passed is False


def test_pbo_receives_inner_holdout_prefix(tmp_path, monkeypatch):
    from alphaloop.diagnostic.holdout import nested_holdout_bounds
    from alphaloop.diagnostic.pbo import PBOResult

    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    runner = _IncompleteThenPass()
    captured: dict[str, list[int]] = {}

    def fake_pbo(returns, **kwargs):
        captured["lens"] = [len(row) for row in returns]
        return PBOResult(
            evaluated=True,
            pbo=0.0,
            passes=True,
            n_strategies=len(returns),
            n_paths=20,
            n_groups=6,
        )

    monkeypatch.setattr(
        "alphaloop.protocol.loop.probability_of_backtest_overfitting",
        fake_pbo,
    )
    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    assert result.research_outcome is ResearchOutcome.FOUND
    inner_end, _, _ = nested_holdout_bounds(300, 252)
    assert inner_end is not None
    assert captured["lens"] == [inner_end, inner_end]
