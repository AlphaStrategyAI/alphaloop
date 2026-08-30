from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from engine.research.clock import TimeBudget
from engine.research.models import (
    Attempt,
    ChangeClass,
    ConfirmKind,
    ConfirmRequest,
    CoverageFloor,
    Research,
    ResearchEvent,
    ResearchStatus,
    ReviewReport,
    RoundDraft,
)
from engine.research.specify import ProposedChange, classify_change
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.review.subagent import ReviewerPort, run_review_gate


class RoundBuilder(Protocol):
    def build(self, research: Research, attempt_number: int) -> RoundDraft:
        """Run gather → specify → simulate daily → score → all verifiers."""
        raise NotImplementedError

    def retry(self, prior: RoundDraft, review: ReviewReport) -> RoundDraft:
        """Choose a different param/model/research auto-change under the same version."""
        raise NotImplementedError

    def next_change(self, accepted: Attempt) -> ProposedChange:
        """Propose the next change; the loop classifies it before proceeding."""
        raise NotImplementedError


@dataclass(slots=True)
class ResearchLoop:
    store: SQLiteStore
    builder: RoundBuilder
    reviewer: ReviewerPort
    budget: TimeBudget
    now: Callable[[], datetime]

    def run_once(self, research_id: str) -> Research:
        research = self.store.load(research_id)
        if research.status is not ResearchStatus.RUNNING:
            return research
        expected_updated_at = research.updated_at
        self.budget.begin(research.status)
        version_number = research.current_version_number
        if version_number is None:
            raise ValueError("running research must have a current version")
        round_number = len(research.versions[version_number - 1].rounds) + 1
        prior_failures = self.store.review_failure_count(
            research.research_id,
            version_number,
            round_number,
        )
        draft = self.builder.build(research, prior_failures + 1)
        outcome = run_review_gate(
            draft,
            self.reviewer,
            self.builder.retry,
            self.now(),
            prior_failures=prior_failures,
            on_attempt=lambda attempt: self.store.record_review_attempt(
                research.research_id,
                version_number,
                round_number,
                attempt,
                self.now(),
            ),
        )
        if outcome.successful_round is None:
            blocked = transition(
                replace(
                    research,
                    consecutive_review_failures=prior_failures + len(outcome.attempts),
                ),
                ResearchEvent.REQUEST_CONFIRM,
                self.now(),
                outcome.confirm_request,
            )
            result = self.budget.finish(blocked)
            self.store.save(result, expected_updated_at)
            return result

        version_index = version_number
        versions = list(research.versions)
        current = versions[version_index - 1]
        versions[version_index - 1] = replace(
            current,
            rounds=current.rounds + (outcome.successful_round,),
        )
        running = replace(
            research,
            versions=tuple(versions),
            consecutive_review_failures=0,
            updated_at=self.now(),
        )
        charged = self.budget.finish(running)
        accepted = outcome.successful_round.accepted_attempt
        floor = charged.brief.coverage_floor.value
        coverage_breached = floor is not None and (
            accepted.simulation.observations < floor.min_years * 252
            or accepted.simulation.covered_assets < floor.min_assets
            or accepted.simulation.missing_pct > floor.max_missing_pct
        )
        if floor is not None and coverage_breached:
            observed_years = max(1, accepted.simulation.observations // 252)
            lowered = CoverageFloor(
                min_assets=accepted.simulation.covered_assets,
                min_years=observed_years,
                max_missing_pct=accepted.simulation.missing_pct,
            )
            request = ConfirmRequest(
                request_id=f"coverage-v{version_number}-r{round_number}",
                kind=ConfirmKind.COVERAGE,
                proposed_change=f"最低历史覆盖从{floor.min_years}年降为{observed_years}年",
                reason="可用日频历史低于已确认的数据覆盖底线",
                effect="确认后开新版本；拒绝则保持底线并寻找其他数据来源",
                change_class=ChangeClass.COVERAGE,
                patch=(("coverage_floor", lowered),),
            )
            result = transition(
                charged,
                ResearchEvent.REQUEST_CONFIRM,
                self.now(),
                request,
            )
        elif accepted.verification.passed:
            result = transition(charged, ResearchEvent.COMPLETE, self.now())
        elif (
            charged.brief.max_effective_hours.value is not None
            and charged.effective_seconds
            >= charged.brief.max_effective_hours.value * 3600
        ):
            result = transition(charged, ResearchEvent.BUDGET_EXHAUSTED, self.now())
        else:
            change = self.builder.next_change(accepted)
            change_class = classify_change(change)
            if change_class in {ChangeClass.ECONOMIC, ChangeClass.COVERAGE}:
                request = ConfirmRequest(
                    request_id=f"change-v{version_number}-r{round_number}",
                    kind=(
                        ConfirmKind.COVERAGE
                        if change_class is ChangeClass.COVERAGE
                        else ConfirmKind.ECONOMIC
                    ),
                    proposed_change=f"{change.field}: {change.before!r} → {change.after!r}",
                    reason="当前冻结验证未全部通过",
                    effect="确认后应用改动并开新版本",
                    change_class=change_class,
                    patch=((change.field, change.after),),
                )
                result = transition(
                    charged,
                    ResearchEvent.REQUEST_CONFIRM,
                    self.now(),
                    request,
                )
            else:
                result = transition(charged, ResearchEvent.AUTO_CONTINUE, self.now())
        self.store.save(result, expected_updated_at)
        return result
