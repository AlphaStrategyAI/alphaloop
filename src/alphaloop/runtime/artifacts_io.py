from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import GateEvidence, evidence_from_dict
from alphaloop.contracts.research_spec import ResearchSpec

_CANDIDATE_COLUMNS = ("trial_id", "kind", "parameters", "revision")
NO_ALPHA_CLAIM = "This report does not claim alpha or future profitability."
MORNING_DETAIL_KEYS = (
    "returns_scope",
    "n_trials",
    "dsr",
    "oos_sharpe_mean",
    "oos_sharpe_median",
    "first_half_sharpe",
    "second_half_sharpe",
    "regime_stable",
    "n_folds",
    "n_positive_folds",
    "majority_stable",
    "cpcv_n_paths",
    "cpcv_n_groups",
    "cpcv_n_test_groups",
    "cpcv_n_positive_paths",
    "cpcv_oos_sharpe_mean",
    "cpcv_oos_sharpe_median",
    "cpcv_passes",
    "pbo",
    "pbo_n_strategies",
    "pbo_n_paths",
    "pbo_passes",
    "holdout_n",
    "holdout_sharpe",
    "holdout_passes",
)


def write_manifest(layout: RunLayout, spec: ResearchSpec, *, engine_version: str) -> Path:
    layout.run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "engine_version": engine_version,
        "seed": spec.seed,
        "spec_id": spec.spec_id,
        "dataset_id": spec.dataset.dataset_id if spec.dataset else None,
        "dataset_sha256": spec.dataset.sha256 if spec.dataset else None,
        "time_budget_s": spec.time_budget_s,
        "cost_budget_usd": spec.cost_budget_usd,
    }
    layout.manifest.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )
    return layout.manifest


def _ledger_rows(layout: RunLayout) -> list[dict[str, object]]:
    if not layout.trial_ledger.is_file():
        return []
    rows: list[dict[str, object]] = []
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


def write_candidates_parquet(layout: RunLayout) -> Path:
    layout.run_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for row in _ledger_rows(layout):
        parameters = row.get("parameters") or {}
        records.append(
            {
                "trial_id": row.get("trial_id"),
                "kind": row.get("kind"),
                "parameters": json.dumps(parameters, sort_keys=True),
                "revision": row.get("revision"),
            }
        )
    frame = pd.DataFrame(records, columns=list(_CANDIDATE_COLUMNS))
    frame.to_parquet(layout.candidates, index=False)
    return layout.candidates


def _format_detail_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".6g")
    return str(value)


def format_gate_line(row: Mapping[str, Any]) -> str:
    name = str(row.get("name") or "")
    verdict = "pass" if row.get("passed") else "fail"
    parts = [f"{name}: {verdict}"]
    detail = row.get("detail") or {}
    if isinstance(detail, Mapping):
        for key in MORNING_DETAIL_KEYS:
            if key in detail:
                parts.append(f"{key}={_format_detail_value(detail[key])}")
    return " · ".join(parts)


def _gate_result_lines(layout: RunLayout) -> list[str]:
    path = layout.evidence / "gates.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    lines: list[str] = []
    for row in payload.get("results") or []:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if not name:
            continue
        lines.append(format_gate_line(row))
    return lines


def _unique_trial_count(layout: RunLayout) -> int:
    ids: list[str] = []
    for row in _ledger_rows(layout):
        trial_id = row.get("trial_id")
        if trial_id:
            ids.append(str(trial_id))
    return len(dict.fromkeys(ids))


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_trial_evidence(layout: RunLayout) -> list[GateEvidence]:
    rows: list[GateEvidence] = []
    trials_dir = layout.evidence / "trials"
    if trials_dir.is_dir():
        for path in sorted(trials_dir.glob("*.json")):
            payload = _read_json_object(path)
            if payload is None:
                continue
            try:
                rows.append(evidence_from_dict(payload))
            except (KeyError, TypeError, ValueError):
                continue
    if rows:
        return rows
    payload = _read_json_object(layout.evidence / "gates.json")
    if payload is None:
        return []
    try:
        return [evidence_from_dict(payload)]
    except (KeyError, TypeError, ValueError):
        return []


def build_funnel(layout: RunLayout) -> dict[str, Any]:
    trials = _load_trial_evidence(layout)
    n_complete = sum(1 for item in trials if item.complete)
    n_passed = sum(1 for item in trials if item.complete and item.all_passed)
    n_failed = sum(1 for item in trials if item.complete and not item.all_passed)
    n_evaluated = max(_unique_trial_count(layout), n_complete)
    failure_counts: dict[str, int] = {}
    for evidence in trials:
        if not evidence.complete or evidence.all_passed:
            continue
        required = set(evidence.required)
        for row in evidence.results:
            if row.name in required and not row.passed:
                name = row.name.value
                failure_counts[name] = failure_counts.get(name, 0) + 1
    dominant_failures = sorted(
        failure_counts, key=lambda name: (-failure_counts[name], name)
    )
    return {
        "n_evaluated": n_evaluated,
        "n_complete": n_complete,
        "n_passed": n_passed,
        "n_failed": n_failed,
        "n_incomplete": max(0, n_evaluated - n_complete),
        "failure_counts": failure_counts,
        "dominant_failures": dominant_failures,
    }


def _qualifying_entry(
    trial_id: str, row: Mapping[str, Any] | None
) -> dict[str, Any]:
    payload = row or {}
    parameters = payload.get("parameters") or {}
    if not isinstance(parameters, dict):
        parameters = {}
    kind = payload.get("kind")
    return {
        "trial_id": trial_id,
        "kind": str(kind) if kind else None,
        "parameters": parameters,
    }


def build_qualifying_candidates(layout: RunLayout) -> list[dict[str, Any]]:
    ledger_by_id: dict[str, dict[str, object]] = {}
    for row in _ledger_rows(layout):
        trial_id = row.get("trial_id")
        if trial_id:
            ledger_by_id[str(trial_id)] = row

    trials_dir = layout.evidence / "trials"
    if trials_dir.is_dir():
        rows: list[dict[str, Any]] = []
        for path in sorted(trials_dir.glob("*.json")):
            payload = _read_json_object(path)
            if payload is None:
                continue
            try:
                evidence = evidence_from_dict(payload)
            except (KeyError, TypeError, ValueError):
                continue
            if evidence.complete and evidence.all_passed:
                tid = path.stem
                rows.append(_qualifying_entry(tid, ledger_by_id.get(tid)))
        return rows

    payload = _read_json_object(layout.evidence / "gates.json")
    if payload is None:
        return []
    try:
        evidence = evidence_from_dict(payload)
    except (KeyError, TypeError, ValueError):
        return []
    if not (evidence.complete and evidence.all_passed):
        return []
    ids = list(ledger_by_id)
    if ids:
        tid = ids[-1]
        return [_qualifying_entry(tid, ledger_by_id.get(tid))]
    return [_qualifying_entry("gates.json", None)]


def write_report(
    layout: RunLayout,
    *,
    research_outcome: str,
    stop_reason: str | None,
    spec: ResearchSpec | None = None,
    n_trials: int | None = None,
) -> Path:
    layout.run_dir.mkdir(parents=True, exist_ok=True)
    if n_trials is None:
        n_trials = _unique_trial_count(layout)
    lines = ["# Research conclusion", "", NO_ALPHA_CLAIM, ""]
    lines.append(f"research_outcome: {research_outcome}")
    if stop_reason is not None:
        lines.append(f"stop_reason: {stop_reason}")
    if spec is not None:
        lines.append(f"spec_id: {spec.spec_id}")
        lines.append(f"seed: {spec.seed}")
        lines.append(f"n_trials: {n_trials}")
        hyp = spec.hypothesis
        lines.extend(
            [
                "",
                "## Frozen hypothesis",
                "",
                f"statement: {hyp.statement}",
                f"economic_logic: {hyp.economic_logic}",
                f"signal_mechanism: {hyp.signal_mechanism}",
                f"market_scope: {hyp.market_scope}",
                f"market_profile: {hyp.market_profile}",
                f"benchmark: {hyp.benchmark}",
            ]
        )
    gate_lines = _gate_result_lines(layout)
    if gate_lines:
        lines.extend(["", "## Gates", ""])
        lines.extend(gate_lines)
    funnel = build_funnel(layout)
    if funnel["n_evaluated"] or funnel["n_complete"]:
        lines.extend(["", "## Elimination funnel", ""])
        lines.append(f"evaluated: {funnel['n_evaluated']}")
        lines.append(f"passed: {funnel['n_passed']}")
        lines.append(f"failed: {funnel['n_failed']}")
        for name in funnel["dominant_failures"]:
            lines.append(f"{name}: {funnel['failure_counts'][name]}")
    qualifying = build_qualifying_candidates(layout)
    lines.extend(["", "## Qualifying candidates", ""])
    if not qualifying:
        lines.append("none")
    else:
        for row in qualifying:
            kind = row.get("kind") or ""
            parameters = row.get("parameters") or {}
            lines.append(f"{row['trial_id']} · {kind} · {parameters}")
    layout.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return layout.report
