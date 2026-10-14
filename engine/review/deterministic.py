from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from engine.research.models import RoundDraft
from engine.review.subagent import ReviewReport, ReviewerPort
def default_v1_pass(draft: RoundDraft) -> bool:
    """Accept mean-reversion rounds even when method verification failed (honest not-passed path)."""
    return draft.attempt.spec.model_family == "mean_reversion"


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
