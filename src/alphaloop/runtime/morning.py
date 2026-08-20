from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import evidence_from_dict, evidence_to_dict
from alphaloop.contracts.status import ResearchOutcome
from alphaloop.protocol.search import method_parameter_grid
from alphaloop.runtime.artifacts_io import build_funnel, build_qualifying_candidates, format_gate_line
from alphaloop.runtime.store import JobRecord

STOP_REASON_ALL_GATES_PASSED = "all_gates_passed"
STOP_REASON_HARD_GATE_FAILED = "hard_gate_failed"
STOP_REASON_INCOMPLETE_EVIDENCE = "incomplete_evidence"

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


def _load_revisions(layout: RunLayout) -> list[dict[str, Any]]:
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
    for row in _load_revisions(layout):
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


def morning_view(job: JobRecord, data_dir: Path) -> dict[str, Any]:
    layout = RunLayout(Path(data_dir) / job.run_id)
    evidence = _load_evidence(layout)
    results = (evidence or {}).get("results") or []
    evidence_lines = [
        format_gate_line(row) for row in results if isinstance(row, dict)
    ]
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
        "hypothesis": asdict(job.spec.hypothesis),
        "evidence": evidence,
        "evidence_lines": evidence_lines,
        "funnel": build_funnel(layout),
        "qualifying_candidates": build_qualifying_candidates(layout),
        "revisions": _load_revisions(layout),
        "queued_hypotheses": _load_queued(layout),
        "stop_reason": _STOP_REASONS[job.research_outcome],
        "report_markdown": _load_report(layout),
    }
