"""Pydantic-free dataclasses for the v0.8 calibration dataset.

We use plain dataclasses (mirrors the v0.6 judge style; v0.9 can migrate
to pydantic if needed). All fields are typed, all are JSON-serializable.

Per PRD § 2 (R-Dataset):

- ``BacktestReport``: the raw markdown body + meta (strategy, asset,
  time period, language, source).
- ``ReviewerScore``: one (reviewer_id, case_id, dimension, score) row
  from the reviewer CSV.
- ``DimensionGroundTruth``: aggregate (median across 3 reviewers) for
  one dimension of one case.
- ``CalibrationCase``: one row of ``dataset.jsonl`` — case_id, the
  report markdown, the 3 dimension ground truths, and meta.
- ``DatasetMeta``: the sidecar ``dataset.meta.json`` — counts, SHA,
  inter-rater α.

Inter-rater α (Krippendorff's α) is computed at build time in
``dataset.build_dataset`` and stored in ``DatasetMeta.inter_rater_alpha``.
We do not require the `krippendorff` PyPI package — α is approximated
for a fixed-nominal/ordinal setting with 3 raters; for v0.8 the value
is treated as informational (see PRD § 3.1 A-1.5).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


DIMENSIONS: tuple[str, ...] = (
    "readability",
    "decision_quality",
    "risk_disclosure",
)
"""The 3 narrative dimensions scored by the judge (PRD § 0)."""

DEFAULT_THRESHOLD: int = 7
"""Per-dimension pass threshold (>=) for the overall judge verdict."""

DEFAULT_REVIEWER_IDS: tuple[str, ...] = ("R1", "R2", "R3")
"""3 reviewers per case per dimension = 900 ratings (100 × 3 × 3)."""

# Drift threshold per PRD Story 8 (10% relative drift on the mean
# blocks the release).
DEFAULT_DRIFT_THRESHOLD: float = 0.10

# Release-gate thresholds (PRD § 2 Story 7).
GATE_PEARSON_MIN: float = 0.70
GATE_AGREEMENT_MIN: float = 0.60


# ---------------------------------------------------------------------------
# BacktestReport (a single simulated/frozen backtest report)
# ---------------------------------------------------------------------------


@dataclass
class BacktestReport:
    """A single backtest report (Markdown body + metadata).

    Attributes:
        case_id: Stable identifier (e.g. ``calib_001``).
        markdown: Full report body. Should contain real Q1–Q7 sections
            for the "good" stratum, or be intentionally degraded for
            the "clearly bad" stratum.
        strategy: alphaloop strategy name
            (e.g. ``momentum_v3``).
        asset_class: One of ``US_equity``, ``EU_equity``, ``crypto``.
        time_period: ``"<YYYY>-<YYYY>"`` (e.g. ``2018-2023``).
        language: ``"en"`` or ``"zh"``.
        source: ``"alphaloop_loop_v071_replay"`` or
            ``"hand_edited_from_<case_id>"``.
    """

    case_id: str
    markdown: str
    strategy: str = "momentum_v3"
    asset_class: str = "US_equity"
    time_period: str = "2018-2023"
    language: str = "en"
    source: str = "alphaloop_loop_v071_replay"

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Reviewer scores
# ---------------------------------------------------------------------------


@dataclass
class ReviewerScore:
    """One row of the reviewer CSV (or JSONL equivalent).

    Attributes:
        reviewer_id: ``"R1"``, ``"R2"``, ``"R3"`` (or named reviewers).
        case_id: Stable identifier matching ``BacktestReport.case_id``.
        dimension: One of ``DIMENSIONS``.
        score: Integer in [1, 10]. Out-of-range values are clamped.
        notes: Optional reviewer note (not used by metrics).
    """

    reviewer_id: str
    case_id: str
    dimension: str
    score: int
    notes: str = ""

    def __post_init__(self) -> None:
        if self.dimension not in DIMENSIONS:
            raise ValueError(
                f"unknown dimension {self.dimension!r}; "
                f"expected one of {DIMENSIONS}"
            )
        try:
            v = int(self.score)
        except (TypeError, ValueError):
            v = 1
        if v < 1:
            v = 1
        if v > 10:
            v = 10
        self.score = v


@dataclass
class DimensionGroundTruth:
    """Aggregate ground truth for one dimension of one case.

    Attributes:
        score: Median across the reviewers (rounded to int).
        reviewer_ids: List of reviewer IDs that contributed scores.
        reviewer_scores: The raw per-reviewer scores, in the same order
            as ``reviewer_ids``.
        conflict: True iff the reviewer scores disagreed by more than
            1 SD (Story "Conflict resolution").
    """

    score: int
    reviewer_ids: list[str] = field(default_factory=list)
    reviewer_scores: list[int] = field(default_factory=list)
    conflict: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# CalibrationCase — one row of dataset.jsonl
# ---------------------------------------------------------------------------


@dataclass
class CalibrationCase:
    """One row of the calibration dataset (one case).

    Attributes:
        case_id: Stable identifier (``calib_001``..``calib_100``).
        report_markdown: The full Markdown to feed to the judge.
        ground_truth: Dict mapping dimension name → DimensionGroundTruth.
            Always contains all 3 dimensions (PRD § 2 Story 2).
        meta: Side metadata dict (strategy, asset class, language, …).
    """

    case_id: str
    report_markdown: str
    ground_truth: dict[str, DimensionGroundTruth]
    meta: dict = field(default_factory=dict)

    def to_jsonl_dict(self) -> dict:
        """Render to a JSONL-friendly dict (ground truth → nested dict)."""
        return {
            "case_id": self.case_id,
            "report_markdown": self.report_markdown,
            "ground_truth": {
                dim: gt.to_dict() for dim, gt in self.ground_truth.items()
            },
            "meta": dict(self.meta),
        }

    @classmethod
    def from_jsonl_dict(cls, d: dict) -> "CalibrationCase":
        gt_raw = d.get("ground_truth", {}) or {}
        ground_truth: dict[str, DimensionGroundTruth] = {}
        for dim in DIMENSIONS:
            if dim not in gt_raw:
                raise ValueError(
                    f"case {d.get('case_id')!r} missing ground truth for {dim!r}"
                )
            row = gt_raw[dim]
            ground_truth[dim] = DimensionGroundTruth(
                score=int(row.get("score", 1)),
                reviewer_ids=list(row.get("reviewer_ids", []) or []),
                reviewer_scores=list(row.get("reviewer_scores", []) or []),
                conflict=bool(row.get("conflict", False)),
            )
        return cls(
            case_id=str(d.get("case_id", "")),
            report_markdown=str(d.get("report_markdown", "")),
            ground_truth=ground_truth,
            meta=dict(d.get("meta", {}) or {}),
        )


# ---------------------------------------------------------------------------
# Dataset metadata
# ---------------------------------------------------------------------------


@dataclass
class DatasetMeta:
    """Sidecar metadata for the calibration dataset.

    Attributes:
        n_cases: Total number of cases (must equal 100 for v0.8).
        strategies: Mapping strategy → count.
        asset_classes: Mapping asset class → count.
        time_periods: Mapping period → count.
        languages: Mapping language → count.
        inter_rater_alpha: Krippendorff's α (approximate for ordinal,
            3 raters; informational; PRD § 3.1 A-1.5).
        dataset_sha256: SHA-256 of the canonical JSONL bytes (PRD § 2
            Story 4 hash pinning).
        version: Dataset version string (``"v1"`` for v0.8).
        degraded_cases: List of case_ids in the "clearly bad" stratum.
    """

    n_cases: int = 0
    strategies: dict[str, int] = field(default_factory=dict)
    asset_classes: dict[str, int] = field(default_factory=dict)
    time_periods: dict[str, int] = field(default_factory=dict)
    languages: dict[str, int] = field(default_factory=dict)
    inter_rater_alpha: float = 0.0
    dataset_sha256: str = ""
    version: str = "v1"
    degraded_cases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DatasetMeta":
        return cls(
            n_cases=int(d.get("n_cases", 0) or 0),
            strategies=dict(d.get("strategies", {}) or {}),
            asset_classes=dict(d.get("asset_classes", {}) or {}),
            time_periods=dict(d.get("time_periods", {}) or {}),
            languages=dict(d.get("languages", {}) or {}),
            inter_rater_alpha=float(d.get("inter_rater_alpha", 0.0) or 0.0),
            dataset_sha256=str(d.get("dataset_sha256", "") or ""),
            version=str(d.get("version", "v1") or "v1"),
            degraded_cases=list(d.get("degraded_cases", []) or []),
        )


def case_id_for_index(idx: int) -> str:
    """Return the canonical ``calib_NNN`` id for a 0-based index."""
    return f"calib_{idx + 1:03d}"