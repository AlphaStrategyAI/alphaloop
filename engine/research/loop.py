from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from engine.portfolio import LEGACY_COST_MODEL, SCHEDULE_COST_MODEL
from engine.research.a1_copy import FROZEN_INPUT_MISSING, STRATEGY_FAMILY_NOT_RUNNABLE
from engine.research.clock import TimeBudget
from engine.research.confirm_evidence import (
    confirm_created_at_after_evidence,
    evidence_refs_from_failed_attempt,
)
from engine.research.coverage import decide_coverage, within_floor
from engine.research.data_port import data_port_for_research
from engine.research.families import is_legacy_mean_reversion
from engine.research.frozen_input import (
    FrozenVersionInput,
    ensure_frozen_version_input,
    simulation_window,
)
from engine.research.gather import (
    DataPort,
    GatherBatch,
    MaterialPort,
    pit_evidence_annotations,
    pit_evidence_from_payloads,
)
from engine.research.candidates import (
    CandidateStop,
    ExploreDataPort,
    discrete_policy,
    evidence_notes_for,
    explore_end_for,
    failed_methods_of,
    fingerprint_spec,
    legacy_next_lookback,
    plan_candidate,
    context_from_attempt,
    freeze_explore_winner,
    model_deadline_seconds,
    _remaining_seconds,
)
from engine.research.honest_stop import (
    can_auto_continue_impl_iteration,
    change_requires_user_confirm,
    default_implementation_next_change,
    implementation_trials_used,
)
from engine.research.models import (
    Attempt,
    ChangeClass,
    ConfirmKind,
    ConfirmRequest,
    CoverageSnapshot,
    EvidenceRef,
    Market,
    Research,
    ResearchAction,
    ResearchEvent,
    ResearchStatus,
    ReviewReport,
    RoundDraft,
)
from engine.research.run_errors import clear_run_errors
from engine.research.simulate import simulate_daily
from engine.research.specify import ModelProposal, ProposedChange, classify_change, specify
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError
from engine.review.subagent import MAX_CONSECUTIVE_REVIEW_FAILURES
from engine.strategy import MeanReversionStrategy, StrategySpec, apply_trading_schedule
from engine.verifiers import (
    PIT_REVISION_V2,
    method_set_excluding_pit,
    recorded_pit_revision,
    run_verifiers,
)

if TYPE_CHECKING:
    from engine.review.subagent import ReviewerPort, ReviewGateOutcome


def _execution_spec(spec: StrategySpec, research: Research) -> StrategySpec:
    """Apply the product cost table without rewriting a stored legacy spec.

    A new confirm sets ``construction_schedule``. An old A-share mean-reversion
    record stays legacy on reverify; the next round built here uses the table.
    """
    if spec.cost_model != LEGACY_COST_MODEL:
        return spec
    cn_legacy_round = (
        spec.universe.market is Market.CN
        and is_legacy_mean_reversion(spec.strategy_family, spec.family_method)
    )
    if research.construction_schedule != SCHEDULE_COST_MODEL and not cn_legacy_round:
        return spec
    return apply_trading_schedule(spec)


def _as_coverage_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def window_for_round(
    research: Research,
    fallback_start: date | None,
    fallback_end: date | None,
) -> tuple[date | None, date | None]:
    """Use the window pinned at confirm so later rounds share that price cache."""
    if research.data_window_start is not None and research.data_window_end is not None:
        return research.data_window_start, research.data_window_end
    return fallback_start, fallback_end


def _coverage_window(simulation: object, fallback: date) -> tuple[date, date]:
    start = _as_coverage_date(getattr(simulation, "start", None))
    end = _as_coverage_date(getattr(simulation, "end", None))
    if start is None or end is None:
        return fallback, fallback
    return start, end


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frozen_hash(snapshot_root: Path, research_id: str, version_number: int) -> str:
    from engine.research.frozen_input import frozen_file_hash, frozen_input_path

    path = frozen_input_path(snapshot_root, research_id, version_number)
    if not path.is_file():
        return ""
    return frozen_file_hash(path)


def _candidate_hash(spec: object, frozen_hash: str) -> str:
    from engine.research.round_store import candidate_hash

    return candidate_hash(spec, frozen_hash)


def _round_from_attempt(
    attempt: Attempt,
    *,
    version_number: int,
    round_number: int,
    now: datetime,
    prior_spec: object | None,
):
    from engine.research.models import RoundV2
    from engine.research.specify import (
        build_implementation_delta,
        build_logic_statement,
        build_trial_counters,
    )

    logic = build_logic_statement(
        attempt.spec.thesis_locked,
        attempt.spec,
        version_number=version_number,
        had_prior_round=round_number > 1,
    )
    delta_prior = prior_spec if round_number > 1 else None
    return RoundV2(
        round_id=f"v{version_number}-r{round_number}",
        number=round_number,
        accepted_attempt=attempt,
        completed_at=now,
        logic_statement=logic,
        implementation_delta=build_implementation_delta(attempt, delta_prior),
        trial_counters=build_trial_counters((attempt,), attempt),
    )


def _row_missing(store: SQLiteStore, research_id: str) -> bool:
    try:
        store.load(research_id)
    except KeyError:
        return True
    return False


def run_review_gate(
    draft: RoundDraft,
    reviewer: ReviewerPort,
    retry_fn: Callable[[RoundDraft, ReviewReport], RoundDraft],
    now: datetime,
    *,
    prior_failures: int = 0,
    on_attempt: Callable[[Attempt], None] | None = None,
    prior_spec: StrategySpec | None = None,
) -> ReviewGateOutcome:
    from engine.review.subagent import run_review_gate as _run_review_gate
    return _run_review_gate(
        draft,
        reviewer,
        retry_fn,
        now,
        prior_failures=prior_failures,
        on_attempt=on_attempt,
        prior_spec=prior_spec,
    )


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
    data_port: DataPort | None
    start: date | None
    end: date | None
    snapshot_root: Path
    on_action: Callable[[ResearchAction], None] | None = None
    recovery_store: object | None = None
    _frozen: FrozenVersionInput | None = None
    _research_id: str = ""
    suggester: object | None = None
    review_opinion: object | None = None
    pending_stop: object | None = None
    _research: Research | None = None
    _input_hash: str = ""

    def _emit(self, action: ResearchAction) -> None:
        if self.on_action is not None:
            self.on_action(action)

    def _claim_step(
        self,
        research_id: str,
        version: int,
        round_number: int,
        attempt: int,
        input_hash: str,
    ) -> None:
        store = self.recovery_store
        claim = getattr(store, "claim_step", None)
        if claim is None or not input_hash:
            return
        claim(research_id, version, round_number, attempt, "simulate", input_hash)

    def _complete_step(
        self,
        research_id: str,
        version: int,
        round_number: int,
        attempt: int,
        input_hash: str,
        result_ref: str,
    ) -> None:
        store = self.recovery_store
        complete = getattr(store, "complete_step", None)
        if complete is None or not input_hash:
            return
        complete(research_id, version, round_number, attempt, "simulate", input_hash, result_ref)

    def _write_evidence(self, batch: GatherBatch) -> tuple[Path, ...]:
        if not batch.materials and not batch.failures:
            return ()
        evidence_root = self.snapshot_root.parent / "materials"
        evidence_root.mkdir(parents=True, exist_ok=True)
        from engine.research.materials_store import write_immutable_material

        paths: list[Path] = []
        for material in batch.materials:
            paths.append(write_immutable_material(evidence_root, material))
        if batch.failures:
            from engine.research.secret_redaction import redact_text

            (evidence_root / "gather-failures.json").write_text(
                json.dumps(
                    {"failures": [redact_text(item) for item in batch.failures]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        return tuple(paths)

    def _spec_patch(self, version: object, *, lock_params: bool) -> dict[str, object]:
        patch = {
            name: value
            for name, value in version.confirmed_changes  # type: ignore[attr-defined]
            if name in {
                "model_family",
                "lookback_days",
                "entry_z",
                "side",
                "max_drawdown_floor",
                "strategy_family",
                "family_method",
                "family_params",
                "primary_factor",
            }
        }
        if lock_params:
            patch.pop("lookback_days", None)
            patch.pop("entry_z", None)
        return patch

    def _materialize_spec(
        self,
        research: Research,
        version: object,
        prior: StrategySpec | None,
        lookback: int,
        entry_z: float,
        *,
        lock_params: bool,
    ) -> StrategySpec:
        proposal = ModelProposal(
            model_family=prior.model_family if prior else "mean_reversion",
            lookback_days=lookback,
            entry_z=entry_z,
            side=prior.side if prior else "long_only",
        )
        spec = specify(research, prior, proposal)
        patch = self._spec_patch(version, lock_params=lock_params)
        if patch:
            spec = replace(spec, **patch)  # type: ignore[arg-type]
        return _execution_spec(spec, research)

    def _persist_plan(
        self,
        research: Research,
        version: int,
        round_number: int,
        plan: object,
        status: str,
    ) -> None:
        store = self.recovery_store
        record = None if store is None else getattr(store, "record_candidate_plan", None)
        if record is None:
            return
        fingerprint = plan.fingerprint or f"stop:{plan.stop_reason}:{round_number}"  # type: ignore[attr-defined]
        record(
            research.research_id,
            version,
            round_number,
            fingerprint,
            status,
            plan.explanation,  # type: ignore[attr-defined]
            {
                "lookback_days": plan.lookback_days,  # type: ignore[attr-defined]
                "entry_z": plan.entry_z,  # type: ignore[attr-defined]
            },
            plan.evidence_ids,  # type: ignore[attr-defined]
            plan.stop_reason,  # type: ignore[attr-defined]
            technical_retry=bool(plan.technical_retry),  # type: ignore[attr-defined]
        )

    def _load_frozen(self, research: Research, version: object, thesis: str, universe: object):
        explore_end = explore_end_for(research)
        start, end = simulation_window(research, self.start, self.end)
        if explore_end is not None and end > explore_end:
            end = explore_end
        live = self.data_port
        if explore_end is not None and live is not None:
            live = ExploreDataPort(live, explore_end)

        def factory():
            inner = data_port_for_research(research)
            if explore_end is None:
                return inner
            return ExploreDataPort(inner, explore_end)

        return ensure_frozen_version_input(
            snapshot_root=self.snapshot_root,
            research=research,
            version_number=version.number,  # type: ignore[attr-defined]
            symbols=universe.symbols,  # type: ignore[attr-defined]
            start=start,
            end=end,
            thesis=thesis,
            material_ports=self.material_ports,
            live_port=live,
            live_port_factory=factory,
        )

    def _plan_after_freeze(
        self,
        research: Research,
        version: object,
        prior: StrategySpec | None,
        frozen_hash: str,
        *,
        required_changes: str | None,
        evidence_attempt: object | None,
        extra_spec: StrategySpec | None = None,
        use_suggester: bool = True,
    ):
        policy = discrete_policy(research)
        assert policy is not None
        prototype = self._materialize_spec(
            research,
            version,
            prior,
            policy.start_lookback_days,
            policy.start_entry_z,
            lock_params=True,
        )
        identity = prototype
        materials = ()
        if self._frozen is not None:
            materials = self._frozen.batch.materials
        extra: set[str] = set()
        if extra_spec is not None:
            extra.add(fingerprint_spec(extra_spec, frozen_hash))
        context = context_from_attempt(
            research,
            identity,
            input_hash=frozen_hash,
            failed_methods=failed_methods_of(evidence_attempt),
            evidence=evidence_notes_for(evidence_attempt, materials),
            store=self.recovery_store,
            have_prior=prior is not None,
            extra_tried=frozenset(extra),
        )
        if prior is not None:
            context = replace(
                context,
                last_lookback=prior.lookback_days,
                last_entry_z=prior.entry_z,
                max_drawdown_floor=prior.max_drawdown_floor,
            )
        suggester = self.suggester if use_suggester and required_changes is None else None
        return plan_candidate(
            research,
            context,
            suggester=suggester,  # type: ignore[arg-type]
            required_changes=required_changes,
        )

    def _verify(
        self,
        simulation: object,
        spec: StrategySpec,
        payloads: tuple[object, ...],
        *,
        pit_revision: str,
    ):
        evidence_as_of, missing_as_of, undated = pit_evidence_from_payloads(
            payloads,
            revision=pit_revision,
        )
        return run_verifiers(
            simulation,
            spec,
            evidence_as_of=evidence_as_of,
            missing_as_of_material_ids=missing_as_of,
            undated_excluded=undated,
            evidence_annotations=pit_evidence_annotations(payloads),
            pit_revision=pit_revision,
        )

    def build(self, research: Research, attempt_number: int) -> RoundDraft:
        thesis = research.brief.thesis.value
        if thesis is None or research.current_version_number is None:
            raise ValueError("running research requires a locked thesis and version")
        version = research.versions[research.current_version_number - 1]
        prior = version.rounds[-1].accepted_attempt.spec if version.rounds else None
        prior_attempt = version.rounds[-1].accepted_attempt if version.rounds else None
        self._research = research
        self._research_id = research.research_id
        universe = research.brief.universe.value
        if universe is None:
            raise ValueError("running research requires a universe")
        self._emit(ResearchAction.GATHER)
        frozen = self._load_frozen(research, version, thesis, universe)
        self._frozen = frozen
        evidence_paths = self._write_evidence(frozen.batch)
        frozen_hash = _frozen_hash(self.snapshot_root, research.research_id, version.number)
        self._input_hash = frozen_hash
        plan = None
        if discrete_policy(research) is None:
            lookback = legacy_next_lookback(
                None if prior is None else prior.lookback_days,
                attempt_number,
            )
            spec = self._materialize_spec(
                research,
                version,
                prior,
                lookback,
                prior.entry_z if prior else 1.0,
                lock_params=False,
            )
        else:
            plan = self._plan_after_freeze(
                research,
                version,
                prior,
                frozen_hash,
                required_changes=None,
                evidence_attempt=prior_attempt,
            )
            round_number = len(version.rounds) + 1
            if plan.stop_reason:
                self._persist_plan(research, version.number, round_number, plan, "stopped")
                raise CandidateStop(plan)
            assert plan.lookback_days is not None and plan.entry_z is not None
            spec = self._materialize_spec(
                research,
                version,
                prior,
                plan.lookback_days,
                plan.entry_z,
                lock_params=True,
            )
            plan = replace(plan, fingerprint=fingerprint_spec(spec, frozen_hash))
            executed = set()
            reader = getattr(self.recovery_store, "executed_candidate_fingerprints", None)
            if reader is not None:
                executed.update(reader(research.research_id, version.number))
            if plan.fingerprint in executed and not plan.technical_retry:
                stopped = replace(
                    plan,
                    stop_reason="repeat",
                    explanation="该候选已经执行过。换措辞或尝试编号不会再模拟一次。",
                )
                self._persist_plan(research, version.number, round_number, stopped, "stopped")
                raise CandidateStop(stopped)
            self._persist_plan(research, version.number, round_number, plan, "planned")
        if not is_legacy_mean_reversion(spec.strategy_family, spec.family_method):
            raise UserFacingError("STRATEGY_FAMILY_NOT_RUNNABLE", STRATEGY_FAMILY_NOT_RUNNABLE)
        self._emit(ResearchAction.SPECIFY)
        strategy = MeanReversionStrategy(spec)
        round_number = len(version.rounds) + 1
        snapshot = self.snapshot_root / (
            f"{research.research_id}-v{version.number}-r{round_number}-a{attempt_number}.csv"
        )
        self.start, self.end = window_for_round(research, self.start, self.end)
        self._emit(ResearchAction.SIMULATE)
        frozen_hash = _frozen_hash(self.snapshot_root, research.research_id, version.number)
        simulate_key = _candidate_hash(spec, frozen_hash)
        self._claim_step(research.research_id, version.number, round_number, attempt_number, simulate_key)
        simulation = simulate_daily(
            strategy,
            frozen,
            frozen.start,
            frozen.end,
            snapshot_path=snapshot,
        )
        self._complete_step(
            research.research_id,
            version.number,
            round_number,
            attempt_number,
            simulate_key,
            _file_sha256(snapshot),
        )
        if plan is not None:
            self._persist_plan(research, version.number, round_number, plan, "executed")
        self._emit(ResearchAction.VERIFY)
        evidence_payloads = tuple(
            json.loads(path.read_text(encoding="utf-8")) for path in evidence_paths
        )
        evidence_as_of, missing_as_of, undated = pit_evidence_from_payloads(
            evidence_payloads,
            revision=PIT_REVISION_V2,
        )
        verification = run_verifiers(
            simulation,
            spec,
            evidence_as_of=evidence_as_of,
            missing_as_of_material_ids=missing_as_of,
            undated_excluded=undated,
            evidence_annotations=pit_evidence_annotations(evidence_payloads),
            pit_revision=PIT_REVISION_V2,
        )
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
        research = self._research
        if research is not None and discrete_policy(research) is not None:
            return self._retry_discrete(prior, review)
        return self._retry_legacy(prior, review)

    def _retry_discrete(self, prior: RoundDraft, review: ReviewReport) -> RoundDraft:
        research = self._research
        frozen = self._frozen
        if research is None or frozen is None or research.current_version_number is None:
            raise UserFacingError("FROZEN_INPUT_MISSING", FROZEN_INPUT_MISSING)
        version = research.versions[research.current_version_number - 1]
        frozen_hash = _frozen_hash(self.snapshot_root, research.research_id, prior.version_number)
        self._input_hash = frozen_hash
        plan = self._plan_after_freeze(
            research,
            version,
            prior.attempt.spec,
            frozen_hash,
            required_changes=review.required_changes,
            evidence_attempt=prior.attempt,
            extra_spec=prior.attempt.spec,
        )
        if plan.stop_reason:
            self._persist_plan(research, prior.version_number, prior.round_number, plan, "stopped")
            raise CandidateStop(plan)
        assert plan.lookback_days is not None and plan.entry_z is not None
        spec = self._materialize_spec(
            research,
            version,
            prior.attempt.spec,
            plan.lookback_days,
            plan.entry_z,
            lock_params=True,
        )
        plan = replace(plan, fingerprint=fingerprint_spec(spec, frozen_hash))
        already = fingerprint_spec(prior.attempt.spec, frozen_hash)
        if plan.technical_retry or plan.fingerprint == already:
            self._persist_plan(research, prior.version_number, prior.round_number, plan, "executed")
            return replace(
                prior,
                attempt=Attempt(
                    attempt_id=f"v{prior.version_number}-r{prior.round_number}-a{prior.attempt.number + 1}",
                    number=prior.attempt.number + 1,
                    change_class=ChangeClass.PARAM,
                    spec=prior.attempt.spec,
                    simulation=prior.attempt.simulation,
                    verification=prior.attempt.verification,
                    data_snapshot_path=prior.attempt.data_snapshot_path,
                    evidence_paths=prior.attempt.evidence_paths,
                ),
            )
        self._persist_plan(research, prior.version_number, prior.round_number, plan, "planned")
        if not is_legacy_mean_reversion(spec.strategy_family, spec.family_method):
            raise UserFacingError("STRATEGY_FAMILY_NOT_RUNNABLE", STRATEGY_FAMILY_NOT_RUNNABLE)
        self._emit(ResearchAction.SPECIFY)
        strategy = MeanReversionStrategy(spec)
        snapshot = self.snapshot_root / (
            f"retry-v{prior.version_number}-r{prior.round_number}-a{prior.attempt.number + 1}.csv"
        )
        self._emit(ResearchAction.SIMULATE)
        simulate_key = _candidate_hash(spec, frozen_hash)
        self._claim_step(
            research.research_id,
            prior.version_number,
            prior.round_number,
            prior.attempt.number + 1,
            simulate_key,
        )
        simulation = simulate_daily(
            strategy,
            frozen,
            frozen.start,
            frozen.end,
            snapshot_path=snapshot,
        )
        self._complete_step(
            research.research_id,
            prior.version_number,
            prior.round_number,
            prior.attempt.number + 1,
            simulate_key,
            _file_sha256(snapshot),
        )
        self._persist_plan(research, prior.version_number, prior.round_number, plan, "executed")
        self._emit(ResearchAction.VERIFY)
        payloads = tuple(
            json.loads(path.read_text(encoding="utf-8"))
            for path in prior.attempt.evidence_paths
        )
        pit_revision = recorded_pit_revision(prior.attempt.verification)
        return replace(
            prior,
            attempt=Attempt(
                attempt_id=f"v{prior.version_number}-r{prior.round_number}-a{prior.attempt.number + 1}",
                number=prior.attempt.number + 1,
                change_class=ChangeClass.PARAM,
                spec=spec,
                simulation=simulation,
                verification=self._verify(
                    simulation,
                    spec,
                    payloads,
                    pit_revision=pit_revision,
                ),
                data_snapshot_path=snapshot,
                evidence_paths=prior.attempt.evidence_paths,
            ),
        )

    def _retry_legacy(self, prior: RoundDraft, review: ReviewReport) -> RoundDraft:
        del review
        frozen = self._frozen
        if frozen is None:
            raise UserFacingError("FROZEN_INPUT_MISSING", FROZEN_INPUT_MISSING)
        self._emit(ResearchAction.SPECIFY)
        spec = replace(
            prior.attempt.spec,
            id=f"{prior.attempt.spec.id}-retry-{prior.attempt.number + 1}",
            lookback_days=prior.attempt.spec.lookback_days + 5,
        )
        if not is_legacy_mean_reversion(spec.strategy_family, spec.family_method):
            raise UserFacingError("STRATEGY_FAMILY_NOT_RUNNABLE", STRATEGY_FAMILY_NOT_RUNNABLE)
        strategy = MeanReversionStrategy(spec)
        snapshot = self.snapshot_root / (
            f"retry-v{prior.version_number}-r{prior.round_number}-a{prior.attempt.number + 1}.csv"
        )
        self._emit(ResearchAction.SIMULATE)
        research_id = getattr(self, "_research_id", "") or prior.attempt.spec.id
        frozen_hash = _frozen_hash(self.snapshot_root, research_id, prior.version_number)
        simulate_key = _candidate_hash(spec, frozen_hash)
        self._claim_step(
            research_id,
            prior.version_number,
            prior.round_number,
            prior.attempt.number + 1,
            simulate_key,
        )
        simulation = simulate_daily(
            strategy,
            frozen,
            frozen.start,
            frozen.end,
            snapshot_path=snapshot,
        )
        self._complete_step(
            research_id,
            prior.version_number,
            prior.round_number,
            prior.attempt.number + 1,
            simulate_key,
            _file_sha256(snapshot),
        )
        self._emit(ResearchAction.VERIFY)
        pit_revision = recorded_pit_revision(prior.attempt.verification)
        payloads = tuple(
            json.loads(path.read_text(encoding="utf-8"))
            for path in prior.attempt.evidence_paths
        )
        evidence_as_of, missing_as_of, undated = pit_evidence_from_payloads(
            payloads,
            revision=pit_revision,
        )
        return replace(
            prior,
            attempt=Attempt(
                attempt_id=f"v{prior.version_number}-r{prior.round_number}-a{prior.attempt.number + 1}",
                number=prior.attempt.number + 1,
                change_class=ChangeClass.PARAM,
                spec=spec,
                simulation=simulation,
                verification=run_verifiers(
                    simulation,
                    spec,
                    evidence_as_of=evidence_as_of,
                    missing_as_of_material_ids=missing_as_of,
                    undated_excluded=undated,
                    evidence_annotations=pit_evidence_annotations(payloads),
                    pit_revision=pit_revision,
                ),
                data_snapshot_path=snapshot,
                evidence_paths=prior.attempt.evidence_paths,
            ),
        )

    def next_change(self, accepted: Attempt) -> ProposedChange:
        research = self._research
        policy = discrete_policy(research) if research is not None else None
        if research is None or policy is None or research.current_version_number is None:
            return default_implementation_next_change(accepted)
        version = research.versions[research.current_version_number - 1]
        plan = self._plan_after_freeze(
            research,
            version,
            accepted.spec,
            self._input_hash,
            required_changes=None,
            evidence_attempt=accepted,
            use_suggester=False,
        )
        if plan.confirm_change is not None:
            self.pending_stop = None
            return plan.confirm_change
        if plan.stop_reason:
            self.pending_stop = plan
            return default_implementation_next_change(accepted)
        self.pending_stop = None
        if plan.lookback_days is not None and plan.lookback_days != accepted.spec.lookback_days:
            return ProposedChange("lookback_days", accepted.spec.lookback_days, plan.lookback_days)
        if plan.entry_z is not None and abs(plan.entry_z - accepted.spec.entry_z) > 1e-9:
            return ProposedChange("entry_z", accepted.spec.entry_z, plan.entry_z)
        return ProposedChange("lookback_days", accepted.spec.lookback_days, plan.lookback_days)


@dataclass(slots=True)
class ResearchLoop:
    store: SQLiteStore
    builder: RoundBuilder
    reviewer: ReviewerPort
    budget: TimeBudget
    now: Callable[[], datetime]

    def _reconcile_time(self, research: Research) -> Research:
        ledger = self.store.effective_seconds_ledger(research.research_id)
        if ledger > research.effective_seconds + 1e-9:
            return replace(research, effective_seconds=ledger)
        return research

    def _backfill_receipts(self, research: Research) -> None:
        from engine.research.round_store import RoundDecision

        for version in research.versions:
            for round_ in version.rounds:
                if self.store.round_receipt(research.research_id, version.number, round_.number):
                    continue
                snapshot = round_.accepted_attempt.data_snapshot_path
                decision = RoundDecision(
                    kind="round_committed",
                    round_id=round_.round_id,
                    attempt_id=round_.accepted_attempt.attempt_id,
                    version_number=version.number,
                    round_number=round_.number,
                    csv_fingerprint=_file_sha256(snapshot) if snapshot is not None else "",
                )
                revision = self.store.revision_of(research.research_id)
                self.store.write_round_receipt(research, decision, revision)

    def run_once(self, research_id: str) -> Research:
        from engine.research.market_data_cancel import (
            MarketDataCancelled,
            bind_active_research,
            reset_active_research,
        )
        from engine.research.removal import ResearchRemoved, research_was_removed
        from engine.research.store import ConcurrentWrite

        token = bind_active_research(research_id)
        started_before = self.budget._started
        try:
            if research_was_removed(research_id):
                raise ResearchRemoved(research_id)
            try:
                return self._run_once_bound(research_id)
            except ResearchRemoved:
                raise
            except (KeyError, ConcurrentWrite, MarketDataCancelled) as exc:
                if research_was_removed(research_id) or _row_missing(self.store, research_id):
                    raise ResearchRemoved(research_id) from exc
                raise
        except ResearchRemoved:
            if started_before is None and self.budget._started is not None:
                self.budget.begin(ResearchStatus.PAUSED)
            raise
        finally:
            reset_active_research(token)

    def _run_once_bound(self, research_id: str) -> Research:
        from engine.research.removal import ResearchRemoved, research_was_removed
        from engine.research.store import ConcurrentWrite

        def abort_if_removed() -> None:
            if research_was_removed(research_id):
                raise ResearchRemoved(research_id)

        try:
            research = self.store.load(research_id)
        except KeyError as exc:
            raise ResearchRemoved(research_id) from exc
        research = self._reconcile_time(research)
        self._backfill_receipts(research)
        if research.status is ResearchStatus.RUNNING:
            from engine.research.e2e_hooks import hold_running_for_e2e

            hold_running_for_e2e()
            if research_was_removed(research_id):
                raise ResearchRemoved(research_id)
        if research.status is ResearchStatus.RUNNING:
            from engine.research.secret_memory import (
                DESKTOP_REQUIRED_CODE,
                DESKTOP_REQUIRED_MESSAGE,
                secret_gate,
            )

            decision = secret_gate(research.required_secret_ids)
            if decision == "wait":
                return research
            if decision == "pause":
                paused = transition(research, ResearchEvent.PAUSE, self.now())
                paused = replace(
                    paused,
                    last_run_error=DESKTOP_REQUIRED_MESSAGE,
                    last_run_error_code=DESKTOP_REQUIRED_CODE,
                )
                self.store.save(paused, research.updated_at)
                return paused
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
            abort_if_removed()
            action = next_action
            try:
                current = self.store.load(research_id)
            except KeyError as exc:
                raise ResearchRemoved(research_id) from exc
            if current.current_action is next_action:
                return
            snapshot = replace(
                current,
                current_action=next_action,
                updated_at=self.now(),
            )
            self.store.save(snapshot, expected_updated_at)
            expected_updated_at = snapshot.updated_at

        def finish(result: Research, decision: object | None = None) -> Research:
            from engine.research.e2e_hooks import crash_barrier
            from engine.research.round_store import RoundDecision, RoundReplay
            from engine.research.user_errors import UserFacingError

            abort_if_removed()
            if entry_running:
                self.budget.checkpoint(research_id, self.store)
                result = self.budget.finish(result, self.store)
            final_action = (
                action if result.status is ResearchStatus.RUNNING else ResearchAction.IDLE
            )
            result = replace(
                result,
                current_action=final_action,
                updated_at=self.now(),
            )
            if not (
                result.status is ResearchStatus.PAUSED and result.last_run_error_code
            ):
                result = clear_run_errors(result)
            chosen = decision if isinstance(decision, RoundDecision) else RoundDecision(kind="tick")
            if chosen.round_id:
                crash_barrier("after_review")
            try:
                revision = self.store.commit_round_decision(
                    result,
                    expected_updated_at=expected_updated_at,
                    expected_revision=entry_revision,
                    decision=chosen,
                )
            except RoundReplay:
                live = self.store.load(research_id)
                self._backfill_receipts(live)
                return live
            except ConcurrentWrite as exc:
                if research_was_removed(research_id) or _row_missing(self.store, research_id):
                    raise ResearchRemoved(research_id) from exc
                return self.store.load(research_id)
            except UserFacingError as exc:
                if exc.code != "DB_BUSY":
                    raise
                paused = transition(
                    replace(
                        research,
                        last_run_error=exc.message,
                        last_run_error_code=exc.code,
                    ),
                    ResearchEvent.PAUSE,
                    self.now(),
                )
                self.store.save(paused, expected_updated_at)
                return paused
            if chosen.round_id:
                crash_barrier("after_round_commit")
                self.store.write_round_receipt(result, chosen, revision)
            return result

        entry_revision = self.store.revision_of(research_id)
        entry_running = research.status is ResearchStatus.RUNNING
        if entry_running:
            self.budget.begin(ResearchStatus.RUNNING, research_id)

        previous_hook = None
        if isinstance(self.builder, DefaultRoundBuilder):
            previous_hook = self.builder.on_action
            self.builder.on_action = persist_action
            self.builder.recovery_store = self.store
        try:
            version_number = research.current_version_number
            if version_number is None:
                raise ValueError("running research must have a current version")
            version = research.versions[version_number - 1]
            round_number = len(version.rounds) + 1
            prior_failures = self.store.review_failure_count(
                research.research_id,
                version_number,
                round_number,
            )
            recovered = self.store.latest_passed_attempt(
                research.research_id,
                version_number,
                round_number,
            )
            if recovered is not None:
                from engine.review.subagent import ReviewGateOutcome

                prior_spec = (
                    version.rounds[-1].accepted_attempt.spec if version.rounds else None
                )
                outcome = ReviewGateOutcome(
                    version_number=version_number,
                    attempts=(recovered,),
                    successful_round=_round_from_attempt(
                        recovered,
                        version_number=version_number,
                        round_number=round_number,
                        now=self.now(),
                        prior_spec=prior_spec,
                    ),
                    confirm_request=None,
                )
            else:
                if prior_failures >= MAX_CONSECUTIVE_REVIEW_FAILURES:
                    max_hours = research.brief.max_effective_hours.value
                    if (
                        max_hours is not None
                        and research.effective_seconds >= max_hours * 3600
                    ):
                        blocked = replace(
                            research,
                            consecutive_review_failures=prior_failures,
                        )
                        ended = transition(
                            blocked,
                            ResearchEvent.BUDGET_EXHAUSTED,
                            self.now(),
                        )
                        return finish(ended)
                    paused = transition(
                        replace(
                            research,
                            consecutive_review_failures=prior_failures,
                            last_run_error="技术重试已达上限，这一轮的失败尝试仍保留，可以恢复。",
                            last_run_error_code="TECHNICAL_RETRY_EXHAUSTED",
                        ),
                        ResearchEvent.PAUSE,
                        self.now(),
                    )
                    from engine.research.round_store import RoundDecision

                    return finish(paused, RoundDecision(kind="technical_retry_exhausted"))
                persist_action(ResearchAction.GATHER)
                self.budget.checkpoint(research_id, self.store)

                def stop_with(plan: object) -> Research:
                    from engine.research.round_store import RoundDecision

                    updated = replace(
                        research,
                        candidate_stop_reason=str(getattr(plan, "stop_reason", "")),
                        candidate_stop_explanation=str(getattr(plan, "explanation", "")),
                    )
                    decision = RoundDecision(kind="candidate_stop")
                    reason = updated.candidate_stop_reason
                    if reason == "model_failure":
                        paused = transition(
                            replace(
                                updated,
                                last_run_error=updated.candidate_stop_explanation,
                                last_run_error_code="CANDIDATE_MODEL_FAILED",
                            ),
                            ResearchEvent.PAUSE,
                            self.now(),
                        )
                        return finish(paused, decision)
                    if reason == "needs_confirm" and getattr(plan, "confirm_change", None) is not None:
                        change = plan.confirm_change  # type: ignore[attr-defined]
                        rounds_now = research.versions[version_number - 1].rounds
                        if not rounds_now:
                            paused = transition(
                                replace(
                                    updated,
                                    last_run_error=updated.candidate_stop_explanation,
                                    last_run_error_code="CANDIDATE_NEEDS_CONFIRM",
                                ),
                                ResearchEvent.PAUSE,
                                self.now(),
                            )
                            return finish(paused, decision)
                        change_class = classify_change(change)
                        recorded_at = rounds_now[-1].completed_at
                        why_change = evidence_refs_from_failed_attempt(
                            rounds_now[-1].accepted_attempt,
                            recorded_at=recorded_at,
                        )
                        created_at = confirm_created_at_after_evidence(why_change, self.now())
                        if change_class is ChangeClass.COVERAGE:
                            confirm_kind = ConfirmKind.COVERAGE
                        elif change_class is ChangeClass.DATA_LINEAGE:
                            confirm_kind = ConfirmKind.DATA_LINEAGE
                        else:
                            confirm_kind = ConfirmKind.ECONOMIC
                        request = ConfirmRequest(
                            request_id=f"change-v{version_number}-r{len(rounds_now)}",
                            kind=confirm_kind,
                            proposed_change=f"{change.field}: {change.before!r} → {change.after!r}",
                            reason=updated.candidate_stop_explanation or "当前冻结验证未全部通过",
                            effect="确认后应用改动并开新版本",
                            change_class=change_class,
                            patch=((change.field, change.after),),
                            why_change=why_change,
                            created_at=created_at,
                        )
                        return finish(
                            transition(updated, ResearchEvent.REQUEST_CONFIRM, self.now(), request),
                            decision,
                        )
                    if reason == "time_budget":
                        return finish(
                            transition(updated, ResearchEvent.BUDGET_EXHAUSTED, self.now()),
                            decision,
                        )
                    return finish(transition(updated, ResearchEvent.COMPLETE, self.now()), decision)

                reviewer = self.reviewer
                if discrete_policy(research) is not None and isinstance(self.builder, DefaultRoundBuilder):
                    from engine.research.candidates import AdjudicatingReviewer
                    from engine.review.deterministic import DeterministicReviewer

                    reviewer = AdjudicatingReviewer(
                        DeterministicReviewer(),
                        self.builder.review_opinion,  # type: ignore[arg-type]
                        store=self.store,
                        research_id=research.research_id,
                        timeout=model_deadline_seconds(_remaining_seconds(research)),
                    )
                try:
                    draft = self.builder.build(research, prior_failures + 1)
                    abort_if_removed()
                    version = research.versions[version_number - 1]
                    prior_spec = (
                        version.rounds[-1].accepted_attempt.spec if version.rounds else None
                    )
                    self.budget.checkpoint(research_id, self.store)
                    outcome = run_review_gate(
                        draft,
                        reviewer,
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
                        prior_spec=prior_spec,
                    )
                except CandidateStop as stop:
                    return stop_with(stop.plan)
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
                return finish(blocked)

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
            from engine.research.data_window import data_window_key_from_research

            window_key = data_window_key_from_research(running)
            charged = running
            accepted = outcome.successful_round.accepted_attempt
            from engine.research.models import MethodRef
            from engine.research.round_store import RoundDecision

            method_refs: tuple[MethodRef, ...] = ()
            if accepted.verification is not None:
                method_refs = tuple(
                    MethodRef(item.verifier_id, item.revision)
                    for item in accepted.verification.results
                )
            round_decision = RoundDecision(
                kind="round_committed",
                round_id=outcome.successful_round.round_id,
                attempt_id=accepted.attempt_id,
                version_number=version_number,
                round_number=round_number,
                window_key=None if window_key is None else window_key.serialize(),
                method_refs=method_refs,
                csv_fingerprint=_file_sha256(accepted.data_snapshot_path)
                if accepted.data_snapshot_path is not None
                else "",
                candidate_hash=_candidate_hash(
                    accepted.spec,
                    _frozen_hash(
                        getattr(self.builder, "snapshot_root", Path()),
                        research.research_id,
                        version_number,
                    )
                    if isinstance(self.builder, DefaultRoundBuilder)
                    else "",
                ),
            )
            floor = charged.brief.coverage_floor.value
            window_start, window_end = _coverage_window(
                accepted.simulation,
                self.now().date(),
            )
            observed = CoverageSnapshot(
                assets=tuple(charged.brief.universe.value.symbols)[: accepted.simulation.covered_assets]
                if charged.brief.universe.value is not None
                else (),
                years=accepted.simulation.observations / 252,
                missing_pct=accepted.simulation.missing_pct,
                start=window_start,
                end=window_end,
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
                    return finish(result, round_decision)
                if not within_floor(observed, floor):
                    raise RuntimeError("below-floor coverage cannot complete or auto-pass")
            method_set = method_set_excluding_pit(
                charged.brief.round1_methods.value or accepted.spec.method_set
            )
            if accepted.verification.passed_for(method_set):
                if discrete_policy(charged) is not None:
                    charged = replace(
                        charged,
                        candidate_stop_reason="all_pass",
                        candidate_stop_explanation="冻结验证已全部通过，停止继续搜索。",
                    )
                    charged = freeze_explore_winner(
                        charged,
                        accepted.spec,
                        getattr(self.builder, "_input_hash", "") or "",
                    )
                result = transition(charged, ResearchEvent.COMPLETE, self.now())
            elif (
                charged.brief.max_effective_hours.value is not None
                and charged.effective_seconds
                >= charged.brief.max_effective_hours.value * 3600
            ):
                if discrete_policy(charged) is not None:
                    charged = replace(
                        charged,
                        candidate_stop_reason="time_budget",
                        candidate_stop_explanation="有效时间已用完。",
                    )
                result = transition(charged, ResearchEvent.BUDGET_EXHAUSTED, self.now())
            else:
                persist_action(ResearchAction.ITERATE)
                if isinstance(self.builder, DefaultRoundBuilder):
                    self.builder._research = charged
                change = self.builder.next_change(accepted)
                pending = getattr(self.builder, "pending_stop", None)
                if pending is not None and getattr(pending, "stop_reason", ""):
                    if isinstance(self.builder, DefaultRoundBuilder):
                        self.builder.pending_stop = None
                    charged = replace(
                        charged,
                        candidate_stop_reason=str(pending.stop_reason),
                        candidate_stop_explanation=str(pending.explanation),
                    )
                    if pending.stop_reason == "time_budget":
                        result = transition(charged, ResearchEvent.BUDGET_EXHAUSTED, self.now())
                    else:
                        result = transition(charged, ResearchEvent.COMPLETE, self.now())
                    return finish(result, round_decision)
                change_class = classify_change(change)
                if change_requires_user_confirm(change):
                    why_change: tuple[EvidenceRef, ...] = ()
                    created_at = self.now()
                    if change_class is not ChangeClass.COVERAGE:
                        recorded_at = outcome.successful_round.completed_at
                        why_change = evidence_refs_from_failed_attempt(
                            accepted,
                            recorded_at=recorded_at,
                        )
                        created_at = confirm_created_at_after_evidence(
                            why_change,
                            self.now(),
                        )
                    if change_class is ChangeClass.COVERAGE:
                        confirm_kind = ConfirmKind.COVERAGE
                    elif change_class is ChangeClass.DATA_LINEAGE:
                        confirm_kind = ConfirmKind.DATA_LINEAGE
                    else:
                        confirm_kind = ConfirmKind.ECONOMIC
                    request = ConfirmRequest(
                        request_id=f"change-v{version_number}-r{round_number}",
                        kind=confirm_kind,
                        proposed_change=f"{change.field}: {change.before!r} → {change.after!r}",
                        reason="当前冻结验证未全部通过",
                        effect="确认后应用改动并开新版本",
                        change_class=change_class,
                        patch=((change.field, change.after),),
                        why_change=why_change,
                        created_at=created_at,
                    )
                    result = transition(
                        charged,
                        ResearchEvent.REQUEST_CONFIRM,
                        self.now(),
                        request,
                    )
                elif can_auto_continue_impl_iteration(charged, change):
                    result = transition(charged, ResearchEvent.AUTO_CONTINUE, self.now())
                else:
                    if discrete_policy(charged) is not None and not charged.candidate_stop_reason:
                        charged = replace(
                            charged,
                            candidate_stop_reason="round_cap",
                            candidate_stop_explanation=(
                                f"已达冻结轮次上限 {implementation_trials_used(charged)}/"
                                f"{charged.implementation_trial_budget}。"
                            ),
                        )
                    result = transition(charged, ResearchEvent.COMPLETE, self.now())
            return finish(result, round_decision)
        finally:
            self.budget._slices.pop(research_id, None)
            if isinstance(self.builder, DefaultRoundBuilder):
                self.builder.on_action = previous_hook
                self.builder.recovery_store = None
