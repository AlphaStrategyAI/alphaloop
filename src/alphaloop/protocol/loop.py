from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

import pandas as pd

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import (
    GateEvidence,
    HardGateName,
    IncompleteEvidenceError,
    evidence_to_dict,
    outcome_from_evidence,
)
from alphaloop.contracts.research_spec import ResearchSpec
from alphaloop.contracts.status import JobStatus, ResearchOutcome
from alphaloop.protocol.dsl import (
    DSL_SCHEMA_VERSION,
    UnsupportedDslError,
    parse_strategy_document,
    target_weights,
)
from alphaloop.protocol.gates import run_hard_gates
from alphaloop.protocol.profiles import get_profile
from alphaloop.protocol.stop import RevisionKind, should_continue


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


def _append_ledger(layout: RunLayout, payload: Mapping[str, Any]) -> None:
    layout.trial_ledger.parent.mkdir(parents=True, exist_ok=True)
    with layout.trial_ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


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
) -> ProtocolResult:
    layout.run_dir.mkdir(parents=True, exist_ok=True)
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
        return ProtocolResult(
            job_status=JobStatus.COMPLETED,
            research_outcome=ResearchOutcome.INCONCLUSIVE,
            candidate_id=None,
            evidence=None,
        )

    required = tuple(HardGateName(name) for name in spec.success_criteria.hard_gates)
    runner = gate_runner or run_hard_gates
    profile = get_profile(spec.hypothesis.market_profile)
    primary = doc.universe[0]
    primary_prices = prices.get(primary, buy_hold_prices)
    candidate_id = _candidate_id(doc.kind, doc.parameters)
    _append_ledger(
        layout,
        {
            "trial_id": candidate_id,
            "kind": doc.kind,
            "parameters": dict(doc.parameters),
            "revision": "none",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    try:
        evidence = runner(
            required,
            prices=primary_prices,
            strategy_returns=primary_prices.pct_change().fillna(0.0),
            buy_hold_prices=buy_hold_prices,
            benchmark_prices=benchmark_prices,
            secondary_frames=secondary_frames,
            n_trials=1,
            profile=profile,
            seed=spec.seed,
            strategy_fn=_strategy_fn_for(doc, prices),
        )
    except IncompleteEvidenceError:
        return ProtocolResult(
            job_status=JobStatus.COMPLETED,
            research_outcome=ResearchOutcome.INCONCLUSIVE,
            candidate_id=candidate_id,
            evidence=None,
        )

    layout.evidence.mkdir(parents=True, exist_ok=True)
    (layout.evidence / "gates.json").write_text(
        json.dumps(evidence_to_dict(evidence), indent=2) + "\n",
        encoding="utf-8",
    )
    remaining_time = float(spec.time_budget_s if clock is None else max(spec.time_budget_s - clock(), 0))
    remaining_cost = spec.cost_budget_usd if remaining_cost_usd is None else remaining_cost_usd
    should_continue(
        remaining_time_s=remaining_time,
        remaining_cost_usd=remaining_cost,
        last_evidence=evidence,
        proposed_kind=RevisionKind.METHOD,
        stop_reason=None,
    )
    outcome = outcome_from_evidence(JobStatus.COMPLETED, evidence)
    return ProtocolResult(
        job_status=JobStatus.COMPLETED,
        research_outcome=outcome,
        candidate_id=candidate_id,
        evidence=evidence,
    )
