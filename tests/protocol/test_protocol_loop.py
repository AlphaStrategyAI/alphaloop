from __future__ import annotations

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


def test_failed_gate_does_not_walk_the_parameter_grid(tmp_path):
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
    assert calls["n"] == 1


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
    assert json.loads(ledger[1])["parameters"] == {"skip": 42}
    evidence = evidence_from_dict(json.loads((layout.evidence / "gates.json").read_text()))
    assert evidence.all_passed is True


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
