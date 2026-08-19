from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional, Sequence

from alphaloop.contracts.gates import GateEvidence
from alphaloop.contracts.research_spec import Hypothesis

FORBIDDEN_CONTINUE_REASONS = frozenset(
    {
        "negative_oos",
        "failed_after_costs",
        "hard_gate_failed",
        "regime_unstable",
        "expand_failed_search",
    }
)

_ECONOMIC_FIELDS = (
    "economic_logic",
    "signal_mechanism",
    "market_scope",
    "benchmark",
)


class RevisionKind(str, Enum):
    METHOD = "method"
    ECONOMIC = "economic"


@dataclass(frozen=True)
class StopDecision:
    continue_search: bool
    queue_for_human: bool
    reason: str


def classify_revision(
    frozen_hypothesis: Hypothesis,
    frozen_hard_gates: Sequence[str],
    proposed: Mapping[str, object],
) -> RevisionKind:
    for field in _ECONOMIC_FIELDS:
        if field in proposed and proposed[field] != getattr(frozen_hypothesis, field):
            return RevisionKind.ECONOMIC
    if "hard_gates" in proposed and tuple(proposed["hard_gates"]) != tuple(frozen_hard_gates):
        return RevisionKind.ECONOMIC
    return RevisionKind.METHOD


def should_continue(
    *,
    remaining_time_s: float,
    remaining_cost_usd: float,
    last_evidence: Optional[GateEvidence],
    proposed_kind: RevisionKind,
    stop_reason: Optional[str],
) -> StopDecision:
    if proposed_kind is RevisionKind.ECONOMIC:
        return StopDecision(
            continue_search=False,
            queue_for_human=True,
            reason="economic_change_queued",
        )
    if stop_reason in FORBIDDEN_CONTINUE_REASONS:
        return StopDecision(
            continue_search=False,
            queue_for_human=False,
            reason=stop_reason,
        )
    if remaining_time_s <= 0 or remaining_cost_usd <= 0:
        return StopDecision(
            continue_search=False,
            queue_for_human=False,
            reason="budget_exhausted",
        )
    if last_evidence is not None and last_evidence.complete and last_evidence.all_passed:
        return StopDecision(
            continue_search=False,
            queue_for_human=False,
            reason="found",
        )
    if (
        last_evidence is not None
        and last_evidence.complete
        and not last_evidence.all_passed
        and proposed_kind is RevisionKind.METHOD
        and stop_reason is None
    ):
        return StopDecision(
            continue_search=False,
            queue_for_human=False,
            reason="hard_gate_failed",
        )
    return StopDecision(
        continue_search=True,
        queue_for_human=False,
        reason="method_repair",
    )
