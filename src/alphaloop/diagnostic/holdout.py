"""Nested final holdout bounds (selection inner prefix + locked suffix)."""
from __future__ import annotations

from typing import Optional

MIN_INNER_BARS = 120
MIN_HOLDOUT_BARS = 30


def nested_holdout_bounds(
    n: int,
    periods_per_year: int,
    *,
    min_inner: int = MIN_INNER_BARS,
    min_holdout: int = MIN_HOLDOUT_BARS,
) -> Optional[tuple[int, int, int]]:
    """Return ``(inner_end, holdout_start, holdout_end)`` or ``None``.

    Holdout length is ``max(min_holdout, periods_per_year // 4)``. An
    embargo of ``max(1, periods_per_year // 52)`` sits between the inner
    prefix and the holdout suffix. ``holdout_end`` equals ``n``.
    """
    if n <= 0 or periods_per_year <= 0:
        return None
    embargo = max(1, periods_per_year // 52)
    holdout = max(min_holdout, periods_per_year // 4)
    inner_end = n - holdout - embargo
    if inner_end < min_inner:
        return None
    holdout_start = n - holdout
    return inner_end, holdout_start, n
