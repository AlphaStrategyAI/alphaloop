from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Sequence

import pandas as pd

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import (
    GateEvidence,
    GateResult,
    HardGateName,
    IncompleteEvidenceError,
    evidence_to_dict,
    outcome_from_evidence,
)
from alphaloop.contracts.research_spec import ResearchSpec
from alphaloop.contracts.status import JobStatus, ResearchOutcome
from alphaloop.diagnostic.holdout import nested_holdout_bounds
from alphaloop.diagnostic.pbo import PBOResult, probability_of_backtest_overfitting
from alphaloop.protocol.dsl import (
    DSL_SCHEMA_VERSION,
    StrategyDocument,
    UnsupportedDslError,
    parse_strategy_document,
    target_weights,
)
from alphaloop.protocol.gates import run_hard_gates
from alphaloop.protocol.profiles import get_profile
from alphaloop.protocol.recommend import followup_hypotheses
from alphaloop.protocol.returns import compute_strategy_returns
from alphaloop.protocol.search import method_parameter_grid
from alphaloop.protocol.stop import (
    FORBIDDEN_CONTINUE_REASONS,
    RevisionKind,
    classify_revision,
    should_continue,
)


@dataclass(frozen=True)
class ProtocolResult:
    job_status: JobStatus
    research_outcome: ResearchOutcome
    candidate_id: Optional[str]
    evidence: Optional[GateEvidence]


def _universe(market_scope: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in market_scope.split(",") if part.strip())


def _candidate_id(kind: str, parameters: Mapping[str, Any]) -> str:
    encoded = json.dumps({"kind": kind, "parameters": dict(parameters)}, sort_keys=True).encode()
    return "c_" + hashlib.sha256(encoded).hexdigest()[:16]


def _write_evidence(layout: RunLayout, candidate_id: str, evidence: GateEvidence) -> None:
    layout.evidence.mkdir(parents=True, exist_ok=True)
    body = json.dumps(evidence_to_dict(evidence), indent=2) + "\n"
    (layout.evidence / "gates.json").write_text(body, encoding="utf-8")
    trials = layout.evidence / "trials"
    trials.mkdir(parents=True, exist_ok=True)
    (trials / f"{candidate_id}.json").write_text(body, encoding="utf-8")


def _append_ledger(layout: RunLayout, payload: Mapping[str, Any]) -> None:
    layout.trial_ledger.parent.mkdir(parents=True, exist_ok=True)
    with layout.trial_ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _ledger_rows(layout: RunLayout) -> list[dict[str, Any]]:
    if not layout.trial_ledger.exists():
        return []
    lines = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _ledger_ids(rows: list[Mapping[str, Any]]) -> list[str]:
    return [str(row["trial_id"]) for row in rows if "trial_id" in row]


def _strategy_fn_for(doc, prices: Mapping[str, pd.Series]):
    primary = next(iter(doc.universe))

    def _fn(series: pd.Series) -> pd.Series:
        mapped = dict(prices)
        mapped[primary] = series
        # walk-forward expects a weight series aligned to `series`
        weights = []
        for stamp in series.index:
            w = target_weights(doc, mapped, stamp)
            weights.append(w.get(primary, 0.0))
        return pd.Series(weights, index=series.index)

    return _fn


def _queued_hypotheses(layout: RunLayout) -> list[dict[str, Any]]:
    if not layout.recommendations.exists():
        return []
    try:
        payload = json.loads(layout.recommendations.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    queued = payload.get("queued_hypotheses") or []
    return [item for item in queued if isinstance(item, dict)]


def _queue_followup(
    layout: RunLayout,
    spec: ResearchSpec,
    evidence: Optional[GateEvidence],
) -> None:
    if evidence is None or not evidence.complete or evidence.all_passed:
        return
    if _queued_hypotheses(layout):
        return
    items = followup_hypotheses(spec, evidence)
    if not items:
        return
    layout.recommendations.write_text(
        json.dumps({"queued_hypotheses": items}, indent=2) + "\n",
        encoding="utf-8",
    )


def _no_evidence(
    layout: RunLayout,
    spec: ResearchSpec,
    *,
    candidate_id: Optional[str],
    evidence: Optional[GateEvidence],
) -> ProtocolResult:
    _queue_followup(layout, spec, evidence)
    return _result(
        research_outcome=ResearchOutcome.NO_EVIDENCE,
        candidate_id=candidate_id,
        evidence=evidence,
    )


def _result(
    *,
    research_outcome: ResearchOutcome,
    candidate_id: Optional[str],
    evidence: Optional[GateEvidence],
) -> ProtocolResult:
    return ProtocolResult(
        job_status=JobStatus.COMPLETED,
        research_outcome=research_outcome,
        candidate_id=candidate_id,
        evidence=evidence,
    )


_PBO_ATTACH_ORDER = (
    HardGateName.DSR,
    HardGateName.WALK_FORWARD,
    HardGateName.VS_RANDOM,
    HardGateName.VS_BUY_HOLD,
    HardGateName.VS_BENCHMARK,
    HardGateName.DATA_CONSISTENCY,
)


def _attach_pbo(evidence: GateEvidence, pbo: PBOResult) -> GateEvidence:
    target = next((name for name in _PBO_ATTACH_ORDER if name in evidence.required), None)
    if target is None:
        return evidence
    extra = {
        "pbo": pbo.pbo,
        "pbo_n_strategies": pbo.n_strategies,
        "pbo_n_paths": pbo.n_paths,
        "pbo_passes": bool(pbo.passes),
    }
    rows: list[GateResult] = []
    for row in evidence.results:
        if row.name is target:
            detail = dict(row.detail)
            detail.update(extra)
            rows.append(
                GateResult(
                    name=row.name,
                    passed=bool(row.passed and pbo.passes),
                    detail=detail,
                )
            )
        else:
            rows.append(row)
    return GateEvidence(results=tuple(rows), required=evidence.required)


def run_protocol(
    spec: ResearchSpec,
    layout: RunLayout,
    *,
    prices: Mapping[str, pd.Series],
    buy_hold_prices: pd.Series,
    benchmark_prices: pd.Series,
    secondary_frames: Optional[Mapping[str, tuple[pd.DataFrame, pd.DataFrame]]] = None,
    clock: Optional[Callable[[], float]] = None,
    gate_runner: Optional[Callable[..., GateEvidence]] = None,
    remaining_cost_usd: Optional[float] = None,
    revision_proposer: Optional[
        Callable[[ResearchSpec, StrategyDocument], Optional[Mapping[str, object]]]
    ] = None,
    completed_trial_ids: Sequence[str] = (),
    on_trial: Optional[Callable[[Mapping[str, Any]], None]] = None,
) -> ProtocolResult:
    layout.run_dir.mkdir(parents=True, exist_ok=True)
    if not layout.recommendations.exists():
        layout.recommendations.write_text(
            json.dumps({"queued_hypotheses": []}, indent=2) + "\n",
            encoding="utf-8",
        )
    try:
        doc = parse_strategy_document(
            {
                "schema_version": DSL_SCHEMA_VERSION,
                "kind": spec.hypothesis.signal_mechanism,
                "parameters": {},
                "universe": list(_universe(spec.hypothesis.market_scope)),
                "market_profile": spec.hypothesis.market_profile,
            }
        )
    except UnsupportedDslError:
        return _result(
            research_outcome=ResearchOutcome.INCONCLUSIVE,
            candidate_id=None,
            evidence=None,
        )

    required = tuple(HardGateName(name) for name in spec.success_criteria.hard_gates)
    runner = gate_runner or run_hard_gates
    profile = get_profile(spec.hypothesis.market_profile)
    remaining_cost = spec.cost_budget_usd if remaining_cost_usd is None else remaining_cost_usd
    last_evidence: Optional[GateEvidence] = None
    last_candidate_id: Optional[str] = None
    completed_skip = set(completed_trial_ids)
    finished_ids: list[str] = list(completed_trial_ids)
    trial_returns: list[pd.Series] = []
    grid = method_parameter_grid(doc.kind)

    for index, parameters in enumerate(grid):
        remaining_time = float(
            spec.time_budget_s if clock is None else spec.time_budget_s - clock()
        )
        if remaining_time <= 0 or remaining_cost <= 0:
            if last_evidence is not None and last_evidence.complete:
                return _result(
                    research_outcome=outcome_from_evidence(JobStatus.COMPLETED, last_evidence),
                    candidate_id=last_candidate_id,
                    evidence=last_evidence,
                )
            return _result(
                research_outcome=ResearchOutcome.INCONCLUSIVE,
                candidate_id=last_candidate_id,
                evidence=None,
            )

        trial_doc = replace(doc, parameters=dict(parameters))
        candidate_id = _candidate_id(trial_doc.kind, trial_doc.parameters)
        if candidate_id in completed_skip:
            continue
        last_candidate_id = candidate_id
        if candidate_id not in set(_ledger_ids(_ledger_rows(layout))):
            _append_ledger(
                layout,
                {
                    "trial_id": candidate_id,
                    "kind": trial_doc.kind,
                    "parameters": dict(trial_doc.parameters),
                    "revision": "none" if index == 0 else "method",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        n_trials = len(dict.fromkeys(_ledger_ids(_ledger_rows(layout))))
        primary = trial_doc.universe[0]
        primary_prices = prices.get(primary, buy_hold_prices)
        strategy_fn = _strategy_fn_for(trial_doc, prices)
        weights = strategy_fn(primary_prices)
        strategy_returns = compute_strategy_returns(
            primary_prices, weights, cost_bps=profile.cost_bps
        )
        trial_returns.append(strategy_returns)
        stop_evidence: Optional[GateEvidence] = None
        try:
            evidence = runner(
                required,
                prices=primary_prices,
                strategy_returns=strategy_returns,
                buy_hold_prices=buy_hold_prices,
                benchmark_prices=benchmark_prices,
                secondary_frames=secondary_frames,
                n_trials=n_trials,
                profile=profile,
                seed=spec.seed,
                strategy_fn=strategy_fn,
            )
        except IncompleteEvidenceError:
            evidence = None

        if evidence is not None:
            _write_evidence(layout, candidate_id, evidence)
            last_evidence = evidence
            stop_evidence = evidence

        if on_trial is not None:
            if candidate_id not in finished_ids:
                finished_ids.append(candidate_id)
            on_trial(
                {
                    "trial_id": candidate_id,
                    "completed_trial_ids": tuple(finished_ids),
                    "n_trials": n_trials,
                }
            )

        if clock is not None:
            remaining_time = float(spec.time_budget_s - clock())
        remaining = sum(
            1
            for later in grid[index + 1 :]
            if _candidate_id(doc.kind, later) not in completed_skip
        )
        decision = should_continue(
            remaining_time_s=remaining_time,
            remaining_cost_usd=remaining_cost,
            last_evidence=stop_evidence,
            proposed_kind=RevisionKind.METHOD,
            stop_reason=None,
            frozen_grid_remaining=remaining,
        )
        if decision.reason == "found":
            if last_evidence is not None and len(trial_returns) >= 2:
                pbo_inputs = trial_returns
                bounds = nested_holdout_bounds(
                    len(trial_returns[-1]), profile.periods_per_year
                )
                if bounds is not None:
                    inner_end, _holdout_start, _holdout_end = bounds
                    pbo_inputs = [row.iloc[:inner_end] for row in trial_returns]
                pbo = probability_of_backtest_overfitting(pbo_inputs)
                if pbo.evaluated:
                    last_evidence = _attach_pbo(last_evidence, pbo)
                    _write_evidence(layout, candidate_id, last_evidence)
                    if not last_evidence.all_passed:
                        return _no_evidence(
                            layout,
                            spec,
                            candidate_id=candidate_id,
                            evidence=last_evidence,
                        )
            return _result(
                research_outcome=ResearchOutcome.FOUND,
                candidate_id=candidate_id,
                evidence=last_evidence,
            )
        if decision.reason in FORBIDDEN_CONTINUE_REASONS:
            return _no_evidence(
                layout,
                spec,
                candidate_id=candidate_id,
                evidence=last_evidence,
            )
        if decision.continue_search:
            if decision.reason == "method_repair" and revision_proposer is not None:
                proposed = revision_proposer(spec, trial_doc)
                if proposed:
                    kind = classify_revision(
                        spec.hypothesis,
                        spec.success_criteria.hard_gates,
                        proposed,
                    )
                    revision_decision = should_continue(
                        remaining_time_s=remaining_time,
                        remaining_cost_usd=remaining_cost,
                        last_evidence=last_evidence,
                        proposed_kind=kind,
                        stop_reason=None,
                    )
                    if revision_decision.queue_for_human:
                        queued = [
                            {"queued_reason": revision_decision.reason, **dict(proposed)}
                        ]
                        layout.recommendations.write_text(
                            json.dumps({"queued_hypotheses": queued}, indent=2) + "\n",
                            encoding="utf-8",
                        )
                        return _result(
                            research_outcome=(
                                outcome_from_evidence(JobStatus.COMPLETED, last_evidence)
                                if last_evidence is not None and last_evidence.complete
                                else ResearchOutcome.INCONCLUSIVE
                            ),
                            candidate_id=candidate_id,
                            evidence=(
                                last_evidence
                                if last_evidence is not None and last_evidence.complete
                                else None
                            ),
                        )
            continue
        break

    if last_evidence is not None and last_evidence.complete and not last_evidence.all_passed:
        return _no_evidence(
            layout,
            spec,
            candidate_id=last_candidate_id,
            evidence=last_evidence,
        )
    return _result(
        research_outcome=ResearchOutcome.INCONCLUSIVE,
        candidate_id=last_candidate_id,
        evidence=last_evidence if last_evidence is not None and last_evidence.complete else None,
    )
