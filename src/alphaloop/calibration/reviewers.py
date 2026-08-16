"""Reviewer scoring logic — median aggregation + conflict resolution.

PRD § 2 Story 2:

- Per-dimension ground truth = **median** across 3 reviewers
  (rounded to nearest integer). Reviewer 1-10 Likert scale.
- Median (not mean) resists extreme misreads.

PRD default answer (Q5): "Ground truth 评分 = Likert 1-10".

Conflict resolution (PRD default answer Q6): "取平均 + 1 SD 内
accept, 否则重审". Translated:
- Compute mean and SD of the 3 reviewer scores.
- If all 3 are within 1 SD of the mean → accept the median.
- Otherwise → flag the case as ``conflict=True``; the median is still
  recorded for completeness, but downstream code can filter on
  ``conflict`` to exclude those cases from metric computation.

This module is **pure functions** — no I/O, no LLM. The build pipeline
in ``dataset.py`` uses them at build time.
"""
from __future__ import annotations

import statistics
from typing import Iterable

from .schema import DIMENSIONS, DimensionGroundTruth, ReviewerScore


def median_score(scores: Iterable[int]) -> int:
    """Return the median of integer scores, rounded to nearest int.

    PRD § 2 Story 2: "median across the 3 reviewers, rounded to
    nearest integer". With 3 integer scores the median is one of the
    inputs (no rounding needed in the 3-rater case), but the function
    still rounds defensively for callers that pass longer lists.
    """
    vals = sorted(int(s) for s in scores)
    if not vals:
        raise ValueError("median_score requires at least 1 score")
    n = len(vals)
    if n % 2 == 1:
        return int(vals[n // 2])
    mid = (vals[n // 2 - 1] + vals[n // 2]) / 2.0
    return int(round(mid))


def resolve_conflicts(scores: Iterable[int]) -> bool:
    """Return True iff the 3 reviewer scores exceed 1 SD of disagreement.

    Per PRD Q6 default: "取平均 + 1 SD 内 accept, 否则重审". A case
    where reviewer spread > 1 SD is flagged for re-review but the
    median is still retained (``conflict=True``).
    """
    vals = [int(s) for s in scores]
    if len(vals) < 2:
        return False
    if len(vals) == 2:
        # With 2 scores, SD is undefined; treat |diff| >= 4 as conflict.
        return abs(vals[0] - vals[1]) >= 4
    mean = statistics.fmean(vals)
    sd = statistics.pstdev(vals)
    for v in vals:
        if abs(v - mean) > sd:
            return True
    return False


def reviewer_scores_to_ground_truth(
    scores: list[ReviewerScore],
    *,
    case_id: str,
) -> dict[str, DimensionGroundTruth]:
    """Build the per-dimension ground-truth dict for one case.

    Args:
        scores: All ReviewerScore rows for the case (3 reviewers ×
            3 dimensions = 9 rows). May include extras (e.g. 2nd-pass
            re-reviews); the most recent score per (reviewer, dim) wins.
        case_id: Expected case_id (asserted).

    Returns:
        Dict mapping each dimension (in DIMENSIONS) to a
        DimensionGroundTruth with the median across reviewers,
        reviewer_ids, raw reviewer_scores, and conflict flag.

    Raises:
        ValueError: if any dimension has fewer than 2 reviewer scores
            (PRD § 2 Story 2 exclusion rule).
    """
    if not all(s.case_id == case_id for s in scores):
        raise ValueError(
            f"score rows do not all belong to case_id={case_id!r}"
        )

    # Bucket: dim → {reviewer_id: latest_score}.
    bucketed: dict[str, dict[str, int]] = {d: {} for d in DIMENSIONS}
    for s in scores:
        bucketed[s.dimension][s.reviewer_id] = s.score

    out: dict[str, DimensionGroundTruth] = {}
    for dim in DIMENSIONS:
        per_reviewer = bucketed[dim]
        if len(per_reviewer) < 2:
            raise ValueError(
                f"case {case_id!r} dim {dim!r}: only "
                f"{len(per_reviewer)} reviewer scores (need >= 2)"
            )
        ids = sorted(per_reviewer.keys())
        vals = [per_reviewer[i] for i in ids]
        median = median_score(vals)
        conflict = resolve_conflicts(vals)
        out[dim] = DimensionGroundTruth(
            score=median,
            reviewer_ids=ids,
            reviewer_scores=vals,
            conflict=conflict,
        )
    return out


# ---------------------------------------------------------------------------
# Convenience: programmatic reviewer simulator (used in tests + CLI smoke)
# ---------------------------------------------------------------------------


def simulate_reviewer(
    *,
    case_id: str,
    reviewer_id: str,
    target_scores: dict[str, int],
    noise_pct: float = 0.0,
    rng=None,
) -> list[ReviewerScore]:
    """Simulate a reviewer's ratings for one case.

    Adds optional noise (in score points) to each target so tests can
    inject reviewer bias. Returns a list of 3 ReviewerScore rows.

    ``noise_pct`` is in [0, 1]; the actual noise is
    ``int(noise_pct * 9)`` score points (range 0–9) added with a
    random sign.
    """
    import random as _random

    if rng is None:
        rng = _random.Random()
    amp = int(round(noise_pct * 9))
    out: list[ReviewerScore] = []
    for dim in DIMENSIONS:
        target = int(target_scores[dim])
        delta = rng.randint(-amp, amp) if amp > 0 else 0
        score = max(1, min(10, target + delta))
        out.append(
            ReviewerScore(
                reviewer_id=reviewer_id,
                case_id=case_id,
                dimension=dim,
                score=score,
            )
        )
    return out