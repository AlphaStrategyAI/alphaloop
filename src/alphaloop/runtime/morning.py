from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import evidence_from_dict, evidence_to_dict
from alphaloop.contracts.status import ResearchOutcome
from alphaloop.protocol.search import method_parameter_grid
from alphaloop.runtime.artifacts_io import (
    build_funnel,
    build_method_revisions,
    build_qualifying_candidates,
    format_gate_line,
    format_primary_evidence,
    format_revision_line,
)
from alphaloop.runtime.store import JobRecord

STOP_REASON_ALL_GATES_PASSED = "all_gates_passed"
STOP_REASON_HARD_GATE_FAILED = "hard_gate_failed"
STOP_REASON_INCOMPLETE_EVIDENCE = "incomplete_evidence"

OUTCOME_GLOSS = {
    "FOUND": (
        "FOUND means every required hard gate is present and passed. "
        "It is not a promise of alpha."
    ),
    "NO_EVIDENCE": (
        "NO_EVIDENCE means a required hard gate failed. "
        "It is not a promise that alpha does not exist."
    ),
    "INCONCLUSIVE": (
        "INCONCLUSIVE means the evidence set is incomplete. "
        "Missing diagnostics cannot produce FOUND."
    ),
    "NONE": (
        "Job status (queued, running, completed, failed, cancelled) "
        "is not the research conclusion."
    ),
}

STATUS_NO_ALPHA = "This status does not claim alpha or future profitability."
EXPORT_NO_ALPHA = "This export does not claim alpha or future profitability."
EMPTY_STATUS_CUE = (
    "No overnight job yet. Preview with alphaloop preview --spec PATH, then freeze "
    "with alphaloop submit --spec PATH. This status does not claim alpha or future "
    "profitability.\n"
)
_PENDING = "(running or not yet terminal)"

_STOP_REASONS = {
    ResearchOutcome.FOUND: STOP_REASON_ALL_GATES_PASSED,
    ResearchOutcome.NO_EVIDENCE: STOP_REASON_HARD_GATE_FAILED,
    ResearchOutcome.INCONCLUSIVE: STOP_REASON_INCOMPLETE_EVIDENCE,
    ResearchOutcome.NONE: None,
}


def _load_evidence(layout: RunLayout) -> Optional[dict[str, Any]]:
    path = layout.evidence / "gates.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        evidence = evidence_from_dict(payload)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    body = evidence_to_dict(evidence)
    body["complete"] = evidence.complete
    body["all_passed"] = evidence.all_passed
    return body


def _load_ledger(layout: RunLayout) -> list[dict[str, Any]]:
    if not layout.trial_ledger.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _load_revisions(layout: RunLayout) -> list[dict[str, Any]]:
    return build_method_revisions(layout)


def _load_queued(layout: RunLayout) -> list[Any]:
    if not layout.recommendations.is_file():
        return []
    try:
        payload = json.loads(layout.recommendations.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    queued = payload.get("queued_hypotheses") or []
    return list(queued) if isinstance(queued, list) else []


def _n_trials(layout: RunLayout) -> int:
    ids: list[str] = []
    for row in _load_ledger(layout):
        trial_id = row.get("trial_id")
        if trial_id:
            ids.append(str(trial_id))
    return len(dict.fromkeys(ids))


def _load_report(layout: RunLayout) -> str:
    if not layout.report.is_file():
        return ""
    try:
        return layout.report.read_text(encoding="utf-8")
    except OSError:
        return ""


def _format_grid_row(parameters: Any) -> str:
    if not isinstance(parameters, dict) or not parameters:
        return "{}"
    return " ".join(f"{key}={parameters[key]}" for key in sorted(parameters))


def format_status_verdict(view: dict[str, Any]) -> str:
    outcome = str(view.get("research_outcome") or "NONE")
    lines = [outcome, OUTCOME_GLOSS.get(outcome, OUTCOME_GLOSS["NONE"])]
    primary = view.get("primary_evidence")
    lines.append("Primary evidence: " + (str(primary) if primary else _PENDING))
    stop = view.get("stop_reason")
    lines.append("Stop reason: " + (str(stop) if stop else _PENDING))
    revisions = view.get("revisions") or []
    if isinstance(revisions, list):
        for row in revisions:
            if not isinstance(row, dict):
                continue
            line = format_revision_line(row)
            if line:
                lines.append("Revision: " + line)
    queued = view.get("queued_hypotheses") or []
    if isinstance(queued, list) and queued:
        first = queued[0]
        statement = first.get("statement") if isinstance(first, dict) else None
        if statement:
            lines.append("Next run: " + str(statement))
    qualifying = view.get("qualifying_candidates") or []
    if outcome == "FOUND" and isinstance(qualifying, list) and qualifying:
        row = qualifying[0] if isinstance(qualifying[0], dict) else {}
        trial = str(row.get("trial_id") or "gates.json")
        kind = str(row.get("kind_label") or row.get("kind") or "")
        params = _format_grid_row(row.get("parameters"))
        lines.append(f"Qualifying: {trial} · {kind} · {params}")
    lines.append("Job status: " + str(view.get("status") or ""))
    lines.append(STATUS_NO_ALPHA)
    return "\n".join(lines) + "\n"


def format_export_handoff(*, candidate_id: str, exported_path: str) -> str:
    return (
        "\n".join(
            [
                "FOUND",
                f"Qualifying: {candidate_id}",
                f"Exported: {exported_path}",
                EXPORT_NO_ALPHA,
            ]
        )
        + "\n"
    )


def replay_view(
    layout: RunLayout,
    *,
    research_outcome: str,
    status: str = "",
) -> dict[str, Any]:
    evidence = _load_evidence(layout)
    funnel = build_funnel(layout)
    try:
        outcome = ResearchOutcome(research_outcome)
    except ValueError:
        outcome = ResearchOutcome.NONE
    return {
        "research_outcome": research_outcome,
        "primary_evidence": format_primary_evidence(
            research_outcome,
            evidence=evidence,
            dominant_failures=funnel["dominant_failures"],
        ),
        "stop_reason": _STOP_REASONS.get(outcome),
        "status": status,
        "queued_hypotheses": _load_queued(layout),
        "qualifying_candidates": build_qualifying_candidates(layout),
        "revisions": build_method_revisions(layout),
    }


def morning_view(job: JobRecord, data_dir: Path) -> dict[str, Any]:
    layout = RunLayout(Path(data_dir) / job.run_id)
    evidence = _load_evidence(layout)
    results = (evidence or {}).get("results") or []
    evidence_lines = [
        format_gate_line(row) for row in results if isinstance(row, dict)
    ]
    funnel = build_funnel(layout)
    return {
        "run_id": job.run_id,
        "status": job.status.value,
        "research_outcome": job.research_outcome.value,
        "spec_id": job.spec.spec_id,
        "seed": job.spec.seed,
        "n_trials": _n_trials(layout),
        "planned_n_trials": len(
            method_parameter_grid(job.spec.hypothesis.signal_mechanism)
        ),
        "error": job.error,
        "recovery_attempts": job.recovery_attempts,
        "heartbeat_at": job.heartbeat_at,
        "hypothesis": asdict(job.spec.hypothesis),
        "evidence": evidence,
        "evidence_lines": evidence_lines,
        "funnel": funnel,
        "primary_evidence": format_primary_evidence(
            job.research_outcome.value,
            evidence=evidence,
            dominant_failures=funnel["dominant_failures"],
        ),
        "qualifying_candidates": build_qualifying_candidates(layout),
        "revisions": _load_revisions(layout),
        "queued_hypotheses": _load_queued(layout),
        "stop_reason": _STOP_REASONS[job.research_outcome],
        "report_markdown": _load_report(layout),
        "time_budget_s": job.spec.time_budget_s,
        "cost_budget_usd": job.spec.cost_budget_usd,
        "dataset": (
            {
                "dataset_id": job.spec.dataset.dataset_id,
                "sha256": job.spec.dataset.sha256,
            }
            if job.spec.dataset is not None
            else None
        ),
    }
