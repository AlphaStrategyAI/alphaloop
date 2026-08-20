from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import evidence_from_dict, outcome_from_evidence
from alphaloop.contracts.research_spec import ResearchSpec
from alphaloop.contracts.status import JobStatus, ResearchOutcome
from alphaloop.runtime.artifacts_io import write_report
from alphaloop.runtime.morning import (
    STOP_REASON_ALL_GATES_PASSED,
    STOP_REASON_HARD_GATE_FAILED,
    STOP_REASON_INCOMPLETE_EVIDENCE,
    replay_view,
)
from alphaloop.runtime.store import JobStore


def rewrite_sealed_report(data_dir: Path, run_id: str) -> dict[str, Any]:
    """Rewrite report.md from sealed artifacts. Does not re-run gates."""
    data_dir = Path(data_dir)
    layout = RunLayout(data_dir / run_id)
    if not layout.run_dir.is_dir():
        raise FileNotFoundError(layout.run_dir)

    spec = None
    spec_path = layout.research_spec
    if spec_path.is_file():
        payload = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("research spec must be a mapping")
        spec = ResearchSpec.from_dict(payload)

    gates_path = layout.evidence / "gates.json"
    outcome = ResearchOutcome.INCONCLUSIVE
    if gates_path.is_file():
        try:
            payload = json.loads(gates_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                evidence = evidence_from_dict(payload)
                if evidence.complete:
                    outcome = outcome_from_evidence(JobStatus.COMPLETED, evidence)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass

    if outcome is ResearchOutcome.FOUND:
        stop_reason = STOP_REASON_ALL_GATES_PASSED
    elif outcome is ResearchOutcome.NO_EVIDENCE:
        stop_reason = STOP_REASON_HARD_GATE_FAILED
    elif outcome is ResearchOutcome.INCONCLUSIVE:
        stop_reason = STOP_REASON_INCOMPLETE_EVIDENCE
    else:
        stop_reason = None

    write_report(
        layout,
        research_outcome=outcome.value,
        stop_reason=stop_reason,
        spec=spec,
    )
    status = ""
    db = data_dir / ".alphaloop" / "state.db"
    if db.is_file():
        try:
            status = JobStore(db, data_dir).get(run_id).status.value
        except KeyError:
            status = ""
    return replay_view(layout, research_outcome=outcome.value, status=status)
