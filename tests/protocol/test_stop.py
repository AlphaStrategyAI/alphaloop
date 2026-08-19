from __future__ import annotations

from alphaloop.contracts.gates import GateEvidence, GateResult, HardGateName
from alphaloop.contracts.research_spec import Hypothesis
from alphaloop.protocol.stop import RevisionKind, classify_revision, should_continue


def _hypothesis(**overrides) -> Hypothesis:
    payload = dict(
        statement="s",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="US large-cap",
        market_profile="us-equity-daily",
        benchmark="SPY",
    )
    payload.update(overrides)
    return Hypothesis(**payload)


def test_signal_mechanism_change_is_economic():
    kind = classify_revision(
        _hypothesis(),
        ("dsr",),
        {"signal_mechanism": "rsi"},
    )
    assert kind is RevisionKind.ECONOMIC


def test_parameter_only_change_is_method():
    kind = classify_revision(
        _hypothesis(),
        ("dsr",),
        {"lookback": 120},
    )
    assert kind is RevisionKind.METHOD


def test_economic_revision_is_queued():
    decision = should_continue(
        remaining_time_s=100,
        remaining_cost_usd=1.0,
        last_evidence=None,
        proposed_kind=RevisionKind.ECONOMIC,
        stop_reason=None,
    )
    assert decision.continue_search is False
    assert decision.queue_for_human is True
    assert decision.reason == "economic_change_queued"


def test_failed_gate_does_not_justify_more_search():
    evidence = GateEvidence(
        results=(GateResult(name=HardGateName.DSR, passed=False, detail={}),),
        required=(HardGateName.DSR,),
    )
    decision = should_continue(
        remaining_time_s=100,
        remaining_cost_usd=1.0,
        last_evidence=evidence,
        proposed_kind=RevisionKind.METHOD,
        stop_reason=None,
    )
    assert decision.continue_search is False
    assert decision.queue_for_human is False
    assert decision.reason == "hard_gate_failed"


def test_explicit_negative_oos_stops():
    decision = should_continue(
        remaining_time_s=100,
        remaining_cost_usd=1.0,
        last_evidence=None,
        proposed_kind=RevisionKind.METHOD,
        stop_reason="negative_oos",
    )
    assert decision.continue_search is False
    assert decision.reason == "negative_oos"


def test_budget_exhausted_stops():
    decision = should_continue(
        remaining_time_s=0,
        remaining_cost_usd=1.0,
        last_evidence=None,
        proposed_kind=RevisionKind.METHOD,
        stop_reason=None,
    )
    assert decision.continue_search is False
    assert decision.reason == "budget_exhausted"


def test_method_repair_with_incomplete_evidence_continues():
    evidence = GateEvidence(
        results=(GateResult(name=HardGateName.DSR, passed=True, detail={}),),
        required=(HardGateName.DSR, HardGateName.WALK_FORWARD),
    )
    decision = should_continue(
        remaining_time_s=10,
        remaining_cost_usd=1.0,
        last_evidence=evidence,
        proposed_kind=RevisionKind.METHOD,
        stop_reason=None,
    )
    assert decision.continue_search is True
    assert decision.reason == "method_repair"
