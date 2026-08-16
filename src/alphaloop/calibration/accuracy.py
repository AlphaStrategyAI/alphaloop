"""Per-dimension accuracy metrics + release gate for v0.8 calibration.

Implements PRD § 2 R-Accuracy (Stories 5–7) and § 3.2 acceptance A-2.x.

Public surface:

- ``compute_pearson``, ``compute_spearman``, ``compute_mae``,
  ``compute_agreement`` — four scalar metrics over two parallel score
  vectors.
- ``compute_confusion_matrix`` — per-dimension TP/TN/FP/FN at the
  pass threshold (Story 6).
- ``gate_v1_release`` — release gate (Story 7): per-dim Pearson ≥ 0.70
  AND within-±2 agreement ≥ 0.60.
- ``CalibrationReport`` — dataclass wrapping the full report shape
  (PRD § 3.2 A-2.2–A-2.5).
- ``build_calibration_report`` — driver: takes judge scores vs ground
  truth and produces a CalibrationReport (with worst-dim callout +
  override flag).
- ``write_calibration_report`` / ``load_calibration_report`` — JSON
  IO matching the schema in PRD § 2 Story 5.

We avoid scipy as a hard runtime dep (the PRD mentions it but also
says hand-rolled Pearson/Spearman is fine). All metrics here use
stdlib + a tiny in-file math helper. This keeps the calibration
package importable from environments where scipy isn't installed
(the dev `pip install -e .` install path is one).
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from .schema import (
    DEFAULT_THRESHOLD,
    DIMENSIONS,
    GATE_AGREEMENT_MIN,
    GATE_PEARSON_MIN,
    CalibrationCase,
)


# ---------------------------------------------------------------------------
# Scalar metrics
# ---------------------------------------------------------------------------


def compute_pearson(judge_scores: Iterable[float], human_scores: Iterable[float]) -> float:
    """Pearson correlation coefficient r in [-1, 1].

    Uses the textbook formula; returns 0.0 when variance is 0 (perfectly
    constant inputs) or when len < 2.
    """
    j = [float(x) for x in judge_scores]
    h = [float(x) for x in human_scores]
    if len(j) != len(h):
        raise ValueError(
            f"length mismatch: judge={len(j)} human={len(h)}"
        )
    n = len(j)
    if n < 2:
        return 0.0
    mean_j = sum(j) / n
    mean_h = sum(h) / n
    cov = sum((j[i] - mean_j) * (h[i] - mean_h) for i in range(n))
    var_j = sum((x - mean_j) ** 2 for x in j)
    var_h = sum((x - mean_h) ** 2 for x in h)
    denom = math.sqrt(var_j * var_h)
    if denom == 0:
        return 0.0
    return cov / denom


def compute_spearman(judge_scores: Iterable[float], human_scores: Iterable[float]) -> float:
    """Spearman ρ — Pearson on the rank vectors."""
    jr = _rank([float(x) for x in judge_scores])
    hr = _rank([float(x) for x in human_scores])
    return compute_pearson(jr, hr)


def _rank(values: list[float]) -> list[float]:
    """Average-rank assignment (handles ties)."""
    sorted_pairs = sorted(enumerate(values), key=lambda p: p[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(sorted_pairs):
        j = i
        while j + 1 < len(sorted_pairs) and sorted_pairs[j + 1][1] == sorted_pairs[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 1-indexed average rank
        for k in range(i, j + 1):
            ranks[sorted_pairs[k][0]] = avg_rank
        i = j + 1
    return ranks


def compute_mae(judge_scores: Iterable[float], human_scores: Iterable[float]) -> float:
    """Mean absolute error over the score pairs."""
    j = [float(x) for x in judge_scores]
    h = [float(x) for x in human_scores]
    if len(j) != len(h):
        raise ValueError(
            f"length mismatch: judge={len(j)} human={len(h)}"
        )
    if not j:
        return 0.0
    return sum(abs(j[i] - h[i]) for i in range(len(j))) / len(j)


def compute_agreement(
    judge_scores: Iterable[float],
    human_scores: Iterable[float],
    *,
    threshold: float = 2.0,
) -> float:
    """Fraction of cases where |judge - human| <= threshold.

    PRD § 2 Story 5: "within ±2 agreement rate".
    """
    j = [float(x) for x in judge_scores]
    h = [float(x) for x in human_scores]
    if len(j) != len(h):
        raise ValueError(
            f"length mismatch: judge={len(j)} human={len(h)}"
        )
    if not j:
        return 0.0
    return sum(1 for a, b in zip(j, h) if abs(a - b) <= threshold) / len(j)


# ---------------------------------------------------------------------------
# Confusion matrix (PRD § 2 Story 6)
# ---------------------------------------------------------------------------


@dataclass
class ConfusionCounts:
    """TP/TN/FP/FN counts at a given threshold."""

    tp: int = 0
    tn: int = 0
    fp: int = 0
    fn: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def compute_confusion_matrix(
    judge_scores: Iterable[float],
    human_scores: Iterable[float],
    *,
    threshold: int = DEFAULT_THRESHOLD,
) -> ConfusionCounts:
    """Binary confusion at ``score >= threshold``.

    - TP: judge >= threshold AND human >= threshold
    - TN: judge <  threshold AND human <  threshold
    - FP: judge >= threshold AND human <  threshold  (judge too lenient)
    - FN: judge <  threshold AND human >= threshold  (judge too strict)
    """
    j = [float(x) for x in judge_scores]
    h = [float(x) for x in human_scores]
    if len(j) != len(h):
        raise ValueError(
            f"length mismatch: judge={len(j)} human={len(h)}"
        )
    out = ConfusionCounts()
    for a, b in zip(j, h):
        j_pass = a >= threshold
        h_pass = b >= threshold
        if j_pass and h_pass:
            out.tp += 1
        elif (not j_pass) and (not h_pass):
            out.tn += 1
        elif j_pass and (not h_pass):
            out.fp += 1
        else:
            out.fn += 1
    return out


# ---------------------------------------------------------------------------
# Per-dim metric bundle
# ---------------------------------------------------------------------------


@dataclass
class DimensionMetrics:
    """All metrics for one dimension of the calibration report."""

    pearson_r: float = 0.0
    spearman_rho: float = 0.0
    mae: float = 0.0
    agreement_within_2: float = 0.0
    confusion: ConfusionCounts = field(default_factory=ConfusionCounts)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["confusion"] = self.confusion.to_dict()
        return d


@dataclass
class CaseRow:
    """One row of the per-case trace in the calibration report."""

    case_id: str
    predicted: dict[str, int]
    ground_truth: dict[str, int]
    delta: dict[str, int]


@dataclass
class CalibrationReport:
    """Top-level calibration report (PRD § 2 Story 5 schema).

    Fields:
        version: Report schema version (``"v0.8-calibration-1"``).
        dataset_sha256: SHA of the dataset that was scored.
        n_cases: Number of cases scored.
        model: The LLM model used (or "skipped" if no LLM ran).
        threshold: The pass threshold for the judge verdict.
        metrics: Per-dimension metric bundle.
        worst_dimension: Name of the dim with the lowest Pearson r.
        worst_dimension_metric: Snapshot of that dim's metrics.
        overall_pass: True iff every dim passes the gate.
        cases: Per-case trace (case_id + predicted + ground_truth + delta).
        prompt_version: The judge prompt version used (Story 11).
        override: Optional override annotation (Story 7).
        created_at: ISO timestamp.
    """

    version: str = "v0.8-calibration-1"
    dataset_sha256: str = ""
    n_cases: int = 0
    model: str = ""
    threshold: int = DEFAULT_THRESHOLD
    metrics: dict[str, DimensionMetrics] = field(default_factory=dict)
    worst_dimension: str = ""
    worst_dimension_metric: DimensionMetrics = field(default_factory=DimensionMetrics)
    overall_pass: bool = False
    cases: list[CaseRow] = field(default_factory=list)
    prompt_version: str = ""
    override: Optional[dict] = None
    created_at: str = ""

    def to_dict(self) -> dict:
        d = {
            "version": self.version,
            "dataset_sha256": self.dataset_sha256,
            "n_cases": self.n_cases,
            "model": self.model,
            "threshold": self.threshold,
            "metrics": {dim: m.to_dict() for dim, m in self.metrics.items()},
            "worst_dimension": self.worst_dimension,
            "worst_dimension_metric": self.worst_dimension_metric.to_dict(),
            "overall_pass": self.overall_pass,
            "prompt_version": self.prompt_version,
            "override": self.override,
            "created_at": self.created_at,
            "cases": [
                {
                    "case_id": c.case_id,
                    "predicted": dict(c.predicted),
                    "ground_truth": dict(c.ground_truth),
                    "delta": dict(c.delta),
                }
                for c in self.cases
            ],
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "CalibrationReport":
        metrics_raw = d.get("metrics", {}) or {}
        metrics: dict[str, DimensionMetrics] = {}
        for dim, row in metrics_raw.items():
            conf = ConfusionCounts(**(row.get("confusion", {}) or {}))
            metrics[dim] = DimensionMetrics(
                pearson_r=float(row.get("pearson_r", 0.0)),
                spearman_rho=float(row.get("spearman_rho", 0.0)),
                mae=float(row.get("mae", 0.0)),
                agreement_within_2=float(row.get("agreement_within_2", 0.0)),
                confusion=conf,
            )
        worst = DimensionMetrics(**(d.get("worst_dimension_metric", {}) or {}))
        cases_raw = d.get("cases", []) or []
        cases: list[CaseRow] = []
        for c in cases_raw:
            cases.append(
                CaseRow(
                    case_id=str(c.get("case_id", "")),
                    predicted=dict(c.get("predicted", {}) or {}),
                    ground_truth=dict(c.get("ground_truth", {}) or {}),
                    delta=dict(c.get("delta", {}) or {}),
                )
            )
        return cls(
            version=str(d.get("version", "v0.8-calibration-1")),
            dataset_sha256=str(d.get("dataset_sha256", "") or ""),
            n_cases=int(d.get("n_cases", 0) or 0),
            model=str(d.get("model", "") or ""),
            threshold=int(d.get("threshold", DEFAULT_THRESHOLD) or DEFAULT_THRESHOLD),
            metrics=metrics,
            worst_dimension=str(d.get("worst_dimension", "") or ""),
            worst_dimension_metric=worst,
            overall_pass=bool(d.get("overall_pass", False)),
            cases=cases,
            prompt_version=str(d.get("prompt_version", "") or ""),
            override=d.get("override"),
            created_at=str(d.get("created_at", "") or ""),
        )


# ---------------------------------------------------------------------------
# Build + write report
# ---------------------------------------------------------------------------


def build_calibration_report(
    *,
    cases: list[CalibrationCase],
    predicted_scores: dict[str, dict[str, int]],
    dataset_sha256_hex: str,
    model: str,
    threshold: int = DEFAULT_THRESHOLD,
    prompt_version: str = "",
    override_reason: Optional[str] = None,
    now_iso: str = "",
) -> CalibrationReport:
    """Build a CalibrationReport from ground truth + predicted scores.

    Args:
        cases: 100 CalibrationCase objects.
        predicted_scores: Mapping case_id → {dim: predicted_score}.
            Must contain every case_id from ``cases``.
        dataset_sha256_hex: SHA-256 hex of the dataset JSONL.
        model: Model name (or "skipped" if no LLM call was made).
        threshold: Pass threshold for the gate.
        prompt_version: Active prompt version (Story 11).
        override_reason: If set, marks the report as overridden with
            this reason and bypasses ``overall_pass`` (Story 7 override
            path). The override is recorded in the report; the printed
            warning is the CLI's responsibility.
        now_iso: ISO timestamp (defaults to "now" UTC if empty).

    Returns:
        CalibrationReport with all per-dim metrics, worst_dim callout,
        confusion matrices, per-case trace, and overall_pass flag.
    """
    if not now_iso:
        from datetime import datetime, timezone

        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    metrics: dict[str, DimensionMetrics] = {}
    for dim in DIMENSIONS:
        j_scores: list[float] = []
        h_scores: list[float] = []
        for case in cases:
            case_pred = predicted_scores.get(case.case_id, {})
            if dim not in case_pred:
                raise ValueError(
                    f"missing predicted score for case {case.case_id!r} dim {dim!r}"
                )
            j_scores.append(int(case_pred[dim]))
            h_scores.append(int(case.ground_truth[dim].score))
        metrics[dim] = DimensionMetrics(
            pearson_r=compute_pearson(j_scores, h_scores),
            spearman_rho=compute_spearman(j_scores, h_scores),
            mae=compute_mae(j_scores, h_scores),
            agreement_within_2=compute_agreement(j_scores, h_scores, threshold=2.0),
            confusion=compute_confusion_matrix(j_scores, h_scores, threshold=threshold),
        )

    # Worst dimension (lowest pearson_r).
    worst_dim = min(
        DIMENSIONS,
        key=lambda d: metrics[d].pearson_r,
    )
    worst_metric = metrics[worst_dim]

    # Per-case trace.
    rows: list[CaseRow] = []
    for case in cases:
        pred = predicted_scores[case.case_id]
        gt = {d: int(case.ground_truth[d].score) for d in DIMENSIONS}
        delta = {d: int(pred[d]) - gt[d] for d in DIMENSIONS}
        rows.append(
            CaseRow(
                case_id=case.case_id,
                predicted={d: int(pred[d]) for d in DIMENSIONS},
                ground_truth=gt,
                delta=delta,
            )
        )

    # Overall pass = gate (unless override).
    overall = _gate(metrics)
    override: Optional[dict] = None
    if override_reason:
        override = {"reason": override_reason, "gate_evaluated_to": overall}
        overall = True  # Story 7: override does not change gate eval,
        # but allows exit 0. We keep gate_evaluated_to for audit.

    report = CalibrationReport(
        dataset_sha256=dataset_sha256_hex,
        n_cases=len(cases),
        model=model,
        threshold=threshold,
        metrics=metrics,
        worst_dimension=worst_dim,
        worst_dimension_metric=worst_metric,
        overall_pass=overall,
        cases=rows,
        prompt_version=prompt_version,
        override=override,
        created_at=now_iso,
    )
    return report


def gate_v1_release(metrics: dict[str, DimensionMetrics]) -> bool:
    """The release gate (PRD § 2 Story 7).

    True iff every dim has Pearson r ≥ GATE_PEARSON_MIN AND within-±2
    agreement ≥ GATE_AGREEMENT_MIN.
    """
    return _gate(metrics)


def _gate(metrics: dict[str, DimensionMetrics]) -> bool:
    for dim in DIMENSIONS:
        m = metrics.get(dim)
        if m is None:
            return False
        if m.pearson_r < GATE_PEARSON_MIN:
            return False
        if m.agreement_within_2 < GATE_AGREEMENT_MIN:
            return False
    return True


def write_calibration_report(
    report: CalibrationReport,
    output_path: str | Path,
) -> Path:
    """Write the calibration report to disk as JSON."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return p


def load_calibration_report(path: str | Path) -> CalibrationReport:
    """Load a calibration report from disk."""
    raw = Path(path).read_text(encoding="utf-8")
    return CalibrationReport.from_dict(json.loads(raw))


# ---------------------------------------------------------------------------
# CLI rendering helpers (used by ``cli.py``)
# ---------------------------------------------------------------------------


def render_report_text(report: CalibrationReport) -> str:
    """Return a human-readable ASCII summary of the report."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("alphaloop v0.8 calibration report")
    lines.append("=" * 70)
    lines.append(f"  cases:         {report.n_cases}")
    lines.append(f"  model:         {report.model or '(skipped)'}")
    lines.append(f"  threshold:     {report.threshold}")
    lines.append(f"  prompt version:{report.prompt_version or '(none)'}")
    lines.append(f"  dataset SHA:   {report.dataset_sha256[:16] or '(none)'}…")
    lines.append("")
    lines.append(
        "  dimension            pearson   spearman   MAE    within±2   "
        "TP  TN  FP  FN"
    )
    lines.append("  " + "-" * 70)
    for dim in DIMENSIONS:
        m = report.metrics.get(dim)
        if m is None:
            continue
        c = m.confusion
        lines.append(
            f"  {dim:<18}  {m.pearson_r:+.3f}    {m.spearman_rho:+.3f}   "
            f"{m.mae:.2f}     {m.agreement_within_2:.2f}     "
            f"{c.tp:>3} {c.tn:>3} {c.fp:>3} {c.fn:>3}"
        )
    lines.append("")
    lines.append(
        f"  worst dimension: {report.worst_dimension or '(none)'} "
        f"(pearson={report.worst_dimension_metric.pearson_r:+.3f})"
    )
    if report.override:
        lines.append("")
        lines.append("  ! OVERRIDE ACTIVE — gate was bypassed with:")
        lines.append(f"      reason: {report.override.get('reason', '')}")
        lines.append(
            f"      gate evaluated to: {report.override.get('gate_evaluated_to')}"
        )
    lines.append("")
    if report.overall_pass:
        lines.append("  >>> GATE PASSED — v1.0 release is unblocked <<<")
    else:
        lines.append("  >>> GATE FAILED — v1.0 release blocked <<<")
        for dim in DIMENSIONS:
            m = report.metrics.get(dim)
            if m is None:
                continue
            if (
                m.pearson_r < GATE_PEARSON_MIN
                or m.agreement_within_2 < GATE_AGREEMENT_MIN
            ):
                lines.append(
                    f"      - {dim}: pearson={m.pearson_r:+.3f} "
                    f"(< {GATE_PEARSON_MIN}), "
                    f"within±2={m.agreement_within_2:.2f} "
                    f"(< {GATE_AGREEMENT_MIN})"
                )
    lines.append("=" * 70)
    return "\n".join(lines)