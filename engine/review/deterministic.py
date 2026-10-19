from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from engine.research.families import is_legacy_mean_reversion
from engine.research.models import RoundDraft
from engine.review.subagent import ReviewReport


def default_v1_pass(draft: RoundDraft) -> bool:
    """Accept the legacy mean-reversion family even when method verification failed."""
    spec = draft.attempt.spec
    return is_legacy_mean_reversion(spec.strategy_family, spec.family_method)


@dataclass(slots=True)
class DeterministicReviewer:
    pass_when: Callable[[RoundDraft], bool] | None = None

    def run(self, round_draft: RoundDraft) -> ReviewReport:
        predicate = self.pass_when or default_v1_pass
        passed = predicate(round_draft)
        if passed:
            return ReviewReport(passed=True, findings=())
        return ReviewReport(
            passed=False,
            findings=(),
            required_changes="deterministic V1 reviewer rejected this draft",
        )
