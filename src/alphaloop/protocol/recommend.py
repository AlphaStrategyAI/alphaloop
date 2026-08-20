from __future__ import annotations

from typing import Optional

from alphaloop.contracts.gates import GateEvidence
from alphaloop.contracts.research_spec import ResearchSpec
from alphaloop.protocol.dsl import DIRECTIONAL_SIGNAL_KINDS

TREND_KINDS = frozenset({"momentum_12_1", "roc", "macd", "atr_breakout"})
REVERSION_KINDS = frozenset({"rsi", "bollinger_zscore", "ohlr_4_pct"})


def counterpart_kind(kind: str) -> Optional[str]:
    if kind in TREND_KINDS:
        nxt = "rsi"
    elif kind in REVERSION_KINDS:
        nxt = "momentum_12_1"
    elif kind == "pairs_spread":
        nxt = "rsi"
    else:
        return None
    if nxt == kind or nxt not in DIRECTIONAL_SIGNAL_KINDS:
        return None
    return nxt


def _dominant_gate_names(evidence: GateEvidence) -> tuple[str, ...]:
    if not evidence.complete or evidence.all_passed:
        return ()
    required = set(evidence.required)
    return tuple(
        row.name.value
        for row in evidence.results
        if row.name in required and not row.passed
    )


def followup_hypotheses(
    spec: ResearchSpec,
    evidence: GateEvidence,
) -> list[dict[str, object]]:
    kind = spec.hypothesis.signal_mechanism
    nxt = counterpart_kind(kind)
    if nxt is None:
        return []
    failed = ", ".join(_dominant_gate_names(evidence)) or "hard gates"
    hyp = spec.hypothesis
    return [
        {
            "queued_reason": "economic_change_queued",
            "statement": (
                f"No evidence for {kind} on the frozen method grid "
                f"(dominant: {failed}). Try {nxt} with the same universe, "
                "profile, and gates. This is not a claim of alpha."
            ),
            "economic_logic": (
                f"Follow-up mechanism after {kind} found no evidence. "
                "Same market; new signal_mechanism requires a new run."
            ),
            "signal_mechanism": nxt,
            "market_scope": hyp.market_scope,
            "market_profile": hyp.market_profile,
            "benchmark": hyp.benchmark,
            "hard_gates": list(spec.success_criteria.hard_gates),
        }
    ]
