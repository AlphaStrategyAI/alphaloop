from alphaloop.contracts.gates import GateResult, HardGateName, evaluate_hard_gates
from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.protocol.dsl import gloss_signal
from alphaloop.protocol.recommend import counterpart_kind, followup_hypotheses


def test_counterpart_kind_table():
    assert counterpart_kind("momentum_12_1") == "rsi"
    assert counterpart_kind("roc") == "rsi"
    assert counterpart_kind("macd") == "rsi"
    assert counterpart_kind("atr_breakout") == "rsi"
    assert counterpart_kind("rsi") == "momentum_12_1"
    assert counterpart_kind("bollinger_zscore") == "momentum_12_1"
    assert counterpart_kind("ohlr_4_pct") == "momentum_12_1"
    assert counterpart_kind("pairs_spread") == "rsi"
    assert counterpart_kind("parkinson_hist_vol") is None
    assert counterpart_kind("obv_slope") is None
    assert counterpart_kind("NotAClass") is None


def test_gloss_signal_matches_form_labels():
    from alphaloop.protocol.dsl import DIRECTIONAL_SIGNAL_KINDS, SIGNAL_GLOSS

    assert gloss_signal("momentum_12_1") == "momentum_12_1 — 12-1 momentum"
    assert gloss_signal("rsi") == "rsi — RSI"
    assert gloss_signal("parkinson_hist_vol") == "parkinson_hist_vol"
    assert set(SIGNAL_GLOSS) == set(DIRECTIONAL_SIGNAL_KINDS)


def test_followup_hypotheses_use_locked_glosses():
    spec = new_research_spec(
        statement="x",
        economic_logic="x",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward"),
        seed=1,
        time_budget_s=30,
        cost_budget_usd=0.0,
    )
    required = tuple(HardGateName(name) for name in spec.success_criteria.hard_gates)
    evidence = evaluate_hard_gates(
        required,
        tuple(
            GateResult(name=name, passed=name is not HardGateName.DSR, detail={})
            for name in required
        ),
    )
    row = followup_hypotheses(spec, evidence)[0]
    assert row["signal_mechanism"] == "rsi"
    assert "momentum_12_1 — 12-1 momentum" in row["statement"]
    assert "rsi — RSI" in row["statement"]
    assert "dsr — Deflated Sharpe Ratio" in row["statement"]
    assert "not a claim of alpha" in row["statement"].lower()
