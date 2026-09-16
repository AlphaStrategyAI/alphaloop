from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from engine.research.clock import TimeBudget
from engine.research.coverage import decide_coverage, within_floor
from engine.research.gather import DataPort, MaterialPort, gather
from engine.research.models import (
    Attempt,
    ChangeClass,
    ConfirmKind,
    ConfirmRequest,
    CoverageSnapshot,
    Research,
    ResearchAction,
    ResearchEvent,
    ResearchStatus,
    ReviewReport,
    RoundDraft,
)
from engine.research.simulate import simulate_daily
from engine.research.specify import ModelProposal, ProposedChange, classify_change, specify
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.review.subagent import MAX_CONSECUTIVE_REVIEW_FAILURES
from engine.strategy import MeanReversionStrategy
from engine.verifiers import run_verifiers

if TYPE_CHECKING:
    from engine.review.subagent import ReviewerPort, ReviewGateOutcome


def run_review_gate(
    draft: RoundDraft,
    reviewer: ReviewerPort,
    retry_fn: Callable[[RoundDraft, ReviewReport], RoundDraft],
    now: datetime,
    *,
    prior_failures: int = 0,
    on_attempt: Callable[[Attempt], None] | None = None,
) -> ReviewGateOutcome:
    from engine.review.subagent import run_review_gate as _run_review_gate
    return _run_review_gate(draft, reviewer, retry_fn, now, prior_failures=prior_failures, on_attempt=on_attempt)


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
class DefaultRoundBuilder:
    material_ports: tuple[MaterialPort, ...]
    data_port: DataPort
    start: date
    end: date
    snapshot_root: Path
    on_action: Callable[[ResearchAction], None] | None = None

    def _emit(self, action: ResearchAction) -> None:
        if self.on_action is not None:
            self.on_action(action)

    def build(self, research: Research, attempt_number: int) -> RoundDraft:
        thesis = research.brief.thesis.value
        if thesis is None or research.current_version_number is None:
            raise ValueError("running research requires a locked thesis and version")
        self._emit(ResearchAction.GATHER)
        materials = gather(thesis, self.material_ports)
        if not materials:
            raise RuntimeError("no public or local evidence was gathered")
        evidence_root = self.snapshot_root.parent / "materials"
        evidence_root.mkdir(parents=True, exist_ok=True)
        evidence_paths = []
        for material in materials:
            digest = hashlib.sha256(material.material_id.encode("utf-8")).hexdigest()
            path = evidence_root / f"{digest}.json"
            path.write_text(
                json.dumps(asdict(material), sort_keys=True, default=str),
                encoding="utf-8",
            )
            evidence_paths.append(path)
        version = research.versions[research.current_version_number - 1]
        prior = version.rounds[-1].accepted_attempt.spec if version.rounds else None
        lookback = prior.lookback_days + 5 if prior else 20 + 5 * (attempt_number - 1)
        proposal = ModelProposal(
            model_family=prior.model_family if prior else "mean_reversion",
            lookback_days=lookback,
            entry_z=prior.entry_z if prior else 1.0,
            side=prior.side if prior else "long_only",
        )
        self._emit(ResearchAction.SPECIFY)
        spec = specify(research, prior, proposal)
        spec_patch = {
            name: value
            for name, value in version.confirmed_changes
            if name in {"model_family", "lookback_days", "entry_z", "side", "max_drawdown_floor"}
        }
        if spec_patch:
            spec = replace(spec, **spec_patch)  # type: ignore[arg-type]
        strategy = MeanReversionStrategy(spec)
        round_number = len(version.rounds) + 1
        snapshot = self.snapshot_root / (
            f"{research.research_id}-v{version.number}-r{round_number}-a{attempt_number}.csv"
        )
        self._emit(ResearchAction.SIMULATE)
        simulation = simulate_daily(
            strategy,
            self.data_port,
            self.start,
            self.end,
            snapshot_path=snapshot,
        )
        self._emit(ResearchAction.VERIFY)
        verification = run_verifiers(simulation, spec)
        return RoundDraft(
            version_number=version.number,
            round_number=round_number,
            attempt=Attempt(
                attempt_id=f"v{version.number}-r{round_number}-a{attempt_number}",
                number=attempt_number,
                change_class=(
                    ChangeClass.MODEL
                    if prior is None and attempt_number == 1
                    else ChangeClass.PARAM
                ),
                spec=spec,
                simulation=simulation,
                verification=verification,
                data_snapshot_path=snapshot,
                evidence_paths=tuple(evidence_paths),
            ),
        )

    def retry(self, prior: RoundDraft, review: ReviewReport) -> RoundDraft:
        self._emit(ResearchAction.SPECIFY)
        spec = replace(
            prior.attempt.spec,
            id=f"{prior.attempt.spec.id}-retry-{prior.attempt.number + 1}",
            lookback_days=prior.attempt.spec.lookback_days + 5,
        )
        strategy = MeanReversionStrategy(spec)
        snapshot = self.snapshot_root / (
            f"retry-v{prior.version_number}-r{prior.round_number}-a{prior.attempt.number + 1}.csv"
        )
        self._emit(ResearchAction.SIMULATE)
        simulation = simulate_daily(
            strategy,
            self.data_port,
            self.start,
            self.end,
            snapshot_path=snapshot,
        )
        self._emit(ResearchAction.VERIFY)
        return replace(
            prior,
            attempt=Attempt(
                attempt_id=f"v{prior.version_number}-r{prior.round_number}-a{prior.attempt.number + 1}",
                number=prior.attempt.number + 1,
                change_class=ChangeClass.PARAM,
                spec=spec,
                simulation=simulation,
                verification=run_verifiers(simulation, spec),
                data_snapshot_path=snapshot,
                evidence_paths=prior.attempt.evidence_paths,
            ),
        )

    def next_change(self, accepted: Attempt) -> ProposedChange:
        return ProposedChange(
            field="lookback_days",
            before=accepted.spec.lookback_days,
            after=accepted.spec.lookback_days + 5,
        )


@dataclass(slots=True)
class ResearchLoop:
    store: SQLiteStore
    builder: RoundBuilder
    reviewer: ReviewerPort
    budget: TimeBudget
    now: Callable[[], datetime]

    def run_once(self, research_id: str) -> Research:
        research = self.store.load(research_id)
        expected_updated_at = research.updated_at
        action = research.current_action
        if research.status is not ResearchStatus.RUNNING:
            if action is ResearchAction.IDLE:
                return research
            idle = replace(
                research,
                current_action=ResearchAction.IDLE,
                updated_at=self.now(),
            )
            self.store.save(idle, expected_updated_at)
            return idle

        def persist_action(next_action: ResearchAction) -> None:
            nonlocal expected_updated_at, action
            action = next_action
            current = self.store.load(research_id)
            if current.current_action is next_action:
                return
            snapshot = replace(
                current,
                current_action=next_action,
                updated_at=self.now(),
            )
            self.store.save(snapshot, expected_updated_at)
            expected_updated_at = snapshot.updated_at

        def finish(result: Research) -> Research:
            final_action = (
                action if result.status is ResearchStatus.RUNNING else ResearchAction.IDLE
            )
            result = replace(result, current_action=final_action)
            self.store.save(result, expected_updated_at)
            return result

        previous_hook = None
        if isinstance(self.builder, DefaultRoundBuilder):
            previous_hook = self.builder.on_action
            self.builder.on_action = persist_action
        try:
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
            if prior_failures >= MAX_CONSECUTIVE_REVIEW_FAILURES:
                blocked = transition(
                    replace(
                        research,
                        consecutive_review_failures=prior_failures,
                    ),
                    ResearchEvent.AUTO_CONTINUE,
                    self.now(),
                )
                return finish(self.budget.finish(blocked))
            persist_action(ResearchAction.GATHER)
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
                if outcome.confirm_request is None:
                    blocked = transition(
                        replace(
                            research,
                            consecutive_review_failures=prior_failures + len(outcome.attempts),
                        ),
                        ResearchEvent.AUTO_CONTINUE,
                        self.now(),
                    )
                else:
                    blocked = transition(
                        replace(
                            research,
                            consecutive_review_failures=prior_failures + len(outcome.attempts),
                        ),
                        ResearchEvent.REQUEST_CONFIRM,
                        self.now(),
                        outcome.confirm_request,
                    )
                return finish(self.budget.finish(blocked))

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
            observed = CoverageSnapshot(
                assets=tuple(charged.brief.universe.value.symbols)[: accepted.simulation.covered_assets]
                if charged.brief.universe.value is not None
                else (),
                years=accepted.simulation.observations / 252,
                missing_pct=accepted.simulation.missing_pct,
                start=self.now().date(),
                end=self.now().date(),
                as_of=self.now(),
            )
            previous = charged.last_coverage
            charged = replace(charged, last_coverage=observed)
            if floor is not None:
                decision = decide_coverage(
                    previous,
                    observed,
                    floor,
                    version_number,
                    round_number,
                )
                if decision.shrink is not None:
                    charged = replace(
                        charged,
                        coverage_history=charged.coverage_history + (decision.shrink,),
                    )
                if decision.action == "confirm":
                    result = transition(
                        charged,
                        ResearchEvent.REQUEST_CONFIRM,
                        self.now(),
                        decision.request,
                    )
                    return finish(result)
                if not within_floor(observed, floor):
                    raise RuntimeError("below-floor coverage cannot complete or auto-pass")
            if accepted.verification.passed:
                result = transition(charged, ResearchEvent.COMPLETE, self.now())
            elif (
                charged.brief.max_effective_hours.value is not None
                and charged.effective_seconds
                >= charged.brief.max_effective_hours.value * 3600
            ):
                result = transition(charged, ResearchEvent.BUDGET_EXHAUSTED, self.now())
            else:
                persist_action(ResearchAction.ITERATE)
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
            return finish(result)
        finally:
            if isinstance(self.builder, DefaultRoundBuilder):
                self.builder.on_action = previous_hook
