from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from engine.research.models import RoundDraft
from engine.review.subagent import ReviewReport, ReviewerPort
from engine.verifiers import method_set_excluding_pit


def default_v1_pass(draft: RoundDraft) -> bool:
    attempt = draft.attempt
    if attempt.spec.model_family != "mean_reversion":
        return False
    method_set = method_set_excluding_pit(attempt.spec.method_set)
    return attempt.verification.passed_for(method_set)


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
