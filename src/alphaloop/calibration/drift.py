"""Drift detection harness for v0.8 (PRD § 2 R-Drift, Stories 8–10).

The drift harness compares the **current** judge scores (freshly
computed by running the judge on the v0.8 dataset) against a **golden
file** frozen at v0.8 ship time. If any dimension's mean score drifts
> 10% relative to the golden, the regression test fails the build.

This module is also used directly by ``tests/test_judge_drift.py``,
which calls ``compare_to_golden(...)`` and asserts on the result.

Public surface:

- ``compute_drift(judge_score, golden_score) -> float``: relative
  drift (judge - golden) / golden. Returns 0.0 when golden is 0.
- ``should_block_release(drift_pct, threshold=0.10) -> bool``: True iff
  ``abs(drift_pct) > threshold``.
- ``compare_to_golden(current_scores, golden_path) -> DriftReport``:
  load the golden JSONL, compute per-dimension drift, return a
  ``DriftReport`` (dataclass) with the report text + per-case rows.
- ``DriftReport``: dataclass with the structured result + the
  pre-formatted ASCII table (Story 9 — alphabetical order).

The golden file format (``golden_scores.jsonl``) is one row per case:

    {"case_id": "calib_001",
     "predicted_readability": 7,
     "predicted_decision_quality": 6,
     "predicted_risk_disclosure": 8}

— no LLM-injected secrets, no markdown bodies, only the scores we
need to compare.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .schema import DEFAULT_DRIFT_THRESHOLD, DIMENSIONS


# ---------------------------------------------------------------------------
# Scalar helpers
# ---------------------------------------------------------------------------


def compute_drift(judge_score: float, golden_score: float) -> float:
    """Relative drift = (judge - golden) / golden.

    Returns 0.0 when ``golden_score`` is exactly 0 (degenerate; treated
    as no-drift to avoid divide-by-zero). Sign carries direction:

    - Positive → judge scores higher than golden.
    - Negative → judge scores lower than golden.
    """
    g = float(golden_score)
    j = float(judge_score)
    if g == 0:
        return 0.0
    return (j - g) / g


def should_block_release(
    drift_pct: float,
    *,
    threshold: float = DEFAULT_DRIFT_THRESHOLD,
) -> bool:
    """True iff ``abs(drift_pct) > threshold``.

    PRD Story 8 / Story 10: threshold = 10% relative drift.
    """
    return abs(float(drift_pct)) > float(threshold)


# ---------------------------------------------------------------------------
# Drift report
# ---------------------------------------------------------------------------


@dataclass
class DriftRow:
    """One row of the per-case drift table (Story 9)."""

    case_id: str
    dim: str
    golden: int
    current: int
    delta: int
    drift_pct: float
    flagged: bool = False  # True iff abs(delta) > 3 (Story 9)


@dataclass
class DriftReport:
    """Structured result of ``compare_to_golden``."""

    version: str = "v0.8-drift-1"
    dataset_path: str = ""
    n_cases: int = 0
    drift_threshold: float = DEFAULT_DRIFT_THRESHOLD
    per_dim_drift_pct: dict[str, float] = field(default_factory=dict)
    rows: list[DriftRow] = field(default_factory=list)
    blocked: bool = False
    block_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "DriftReport":
        rows_raw = d.get("rows", []) or []
        rows = [
            DriftRow(
                case_id=str(r.get("case_id", "")),
                dim=str(r.get("dim", "")),
                golden=int(r.get("golden", 0) or 0),
                current=int(r.get("current", 0) or 0),
                delta=int(r.get("delta", 0) or 0),
                drift_pct=float(r.get("drift_pct", 0.0) or 0.0),
                flagged=bool(r.get("flagged", False)),
            )
            for r in rows_raw
        ]
        return cls(
            version=str(d.get("version", "v0.8-drift-1")),
            dataset_path=str(d.get("dataset_path", "") or ""),
            n_cases=int(d.get("n_cases", 0) or 0),
            drift_threshold=float(d.get("drift_threshold", DEFAULT_DRIFT_THRESHOLD) or DEFAULT_DRIFT_THRESHOLD),
            per_dim_drift_pct=dict(d.get("per_dim_drift_pct", {}) or {}),
            rows=rows,
            blocked=bool(d.get("blocked", False)),
            block_reasons=list(d.get("block_reasons", []) or []),
        )


# ---------------------------------------------------------------------------
# Compare current vs golden
# ---------------------------------------------------------------------------


def load_golden_scores(golden_path: str | Path) -> dict[str, dict[str, int]]:
    """Load the golden JSONL into a dict[case_id][dim] -> int."""
    rows: dict[str, dict[str, int]] = {}
    with Path(golden_path).open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            cid = str(d["case_id"])
            rows[cid] = {
                "readability": int(d["predicted_readability"]),
                "decision_quality": int(d["predicted_decision_quality"]),
                "risk_disclosure": int(d["predicted_risk_disclosure"]),
            }
    return rows


def compare_to_golden(
    current_scores: dict[str, dict[str, int]],
    golden_path: str | Path,
    *,
    threshold: float = DEFAULT_DRIFT_THRESHOLD,
    dataset_path: str = "",
) -> DriftReport:
    """Compare current scores to the golden file.

    Args:
        current_scores: Mapping case_id → {dim: predicted_int}.
        golden_path: Path to the golden JSONL file.
        threshold: Drift threshold (default 0.10 per PRD Story 8).
        dataset_path: Path to the calibration dataset (recorded in
            the report; cosmetic only).

    Behavior:

    - Cases are sorted alphabetically by ``case_id`` (Story 9).
    - Per-dim mean drift (across all cases) is computed and compared
      against the threshold.
    - If any dim exceeds the threshold, ``blocked=True`` with a
      descriptive reason listing dim, drift %, golden mean, current
      mean (Story 10 banner).
    - Per-case rows where ``abs(delta) > 3`` are flagged with
      ``**`` in the rendered text (Story 9).
    """
    golden = load_golden_scores(golden_path)
    common = sorted(set(current_scores.keys()) & set(golden.keys()))
    missing_in_golden = sorted(set(current_scores.keys()) - set(golden.keys()))
    missing_in_current = sorted(set(golden.keys()) - set(current_scores.keys()))

    rows: list[DriftRow] = []
    per_dim_sums: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    for cid in common:
        for dim in DIMENSIONS:
            g = int(golden[cid][dim])
            c = int(current_scores[cid][dim])
            delta = c - g
            drift = compute_drift(c, g)
            rows.append(
                DriftRow(
                    case_id=cid,
                    dim=dim,
                    golden=g,
                    current=c,
                    delta=delta,
                    drift_pct=drift,
                    flagged=abs(delta) > 3,
                )
            )
            per_dim_sums[dim].append(drift)

    per_dim_drift_pct: dict[str, float] = {
        dim: (sum(per_dim_sums[dim]) / len(per_dim_sums[dim]) if per_dim_sums[dim] else 0.0)
        for dim in DIMENSIONS
    }

    block_reasons: list[str] = []
    blocked = False
    golden_means: dict[str, float] = {}
    current_means: dict[str, float] = {}
    for dim in DIMENSIONS:
        if common:
            gm = sum(int(golden[cid][dim]) for cid in common) / len(common)
            cm = sum(int(current_scores[cid][dim]) for cid in common) / len(common)
        else:
            gm, cm = 0.0, 0.0
        golden_means[dim] = gm
        current_means[dim] = cm
        if should_block_release(per_dim_drift_pct[dim], threshold=threshold):
            blocked = True
            block_reasons.append(
                f"{dim}: drift {per_dim_drift_pct[dim]:+.1%} "
                f"(golden mean {gm:.2f}, current mean {cm:.2f}, threshold {threshold:.0%})"
            )
    if missing_in_golden:
        blocked = True
        block_reasons.append(
            f"{len(missing_in_golden)} cases in current missing from golden "
            f"(first 5: {missing_in_golden[:5]})"
        )
    if missing_in_current:
        block_reasons.append(
            f"{len(missing_in_current)} golden cases missing from current "
            f"(first 5: {missing_in_current[:5]})"
        )

    return DriftReport(
        dataset_path=str(dataset_path or golden_path),
        n_cases=len(common),
        drift_threshold=threshold,
        per_dim_drift_pct=per_dim_drift_pct,
        rows=rows,
        blocked=blocked,
        block_reasons=block_reasons,
    )


def render_drift_text(report: DriftReport) -> str:
    """Render the ASCII drift table (Story 9 — alphabetical order)."""
    out: list[str] = []
    out.append("=" * 70)
    out.append("alphaloop v0.8 drift report (alphabetical by case_id)")
    out.append("=" * 70)
    out.append(
        f"  cases:        {report.n_cases}\n"
        f"  threshold:    {report.drift_threshold:.0%}\n"
        f"  blocked:      {report.blocked}"
    )
    out.append("")
    out.append("  per-dimension drift (relative to golden):")
    for dim in DIMENSIONS:
        out.append(
            f"    {dim:<18} {report.per_dim_drift_pct.get(dim, 0.0):+.2%}"
        )
    out.append("")
    out.append("  case_id             dim                golden  current  delta   drift")
    out.append("  " + "-" * 70)
    for r in sorted(report.rows, key=lambda x: (x.case_id, x.dim)):
        flag = "  **" if r.flagged else "    "
        out.append(
            f"  {r.case_id:<18} {r.dim:<18} {r.golden:>6}  {r.current:>7}  "
            f"{r.delta:+5d}  {r.drift_pct:+.2%}{flag}"
        )
    if report.blocked:
        out.append("")
        out.append("=" * 70)
        out.append("JUDGE DRIFT DETECTED — release blocked")
        out.append("=" * 70)
        for reason in report.block_reasons:
            out.append(f"  - {reason}")
        out.append("")
        out.append("Likely cause: LLM provider model swap or finetune.")
        out.append("Action:      re-run calibration, re-freeze golden file, or")
        out.append("             document override.")
    else:
        out.append("")
        out.append("  Drift within threshold — release not blocked.")
    out.append("=" * 70)
    return "\n".join(out)


def write_drift_report(report: DriftReport, output_path: str | Path) -> Path:
    """Write the drift report as JSON."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return p


def write_golden_scores(
    scores: dict[str, dict[str, int]],
    golden_path: str | Path,
) -> Path:
    """Write the golden JSONL (used at v0.8 ship time)."""
    p = Path(golden_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for cid in sorted(scores.keys()):
            row = scores[cid]
            f.write(
                json.dumps(
                    {
                        "case_id": cid,
                        "predicted_readability": int(row["readability"]),
                        "predicted_decision_quality": int(row["decision_quality"]),
                        "predicted_risk_disclosure": int(row["risk_disclosure"]),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            f.write("\n")
    return p