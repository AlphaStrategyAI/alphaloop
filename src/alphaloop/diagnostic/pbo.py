"""Probability of backtest overfitting (Bailey & López de Prado, 2014)."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb
from typing import Sequence

import numpy as np
import pandas as pd

from alphaloop.diagnostic.cv import (
    DEFAULT_CPCV_GROUPS,
    MIN_CPCV_GROUP_BARS,
    _annualized_sharpe,
    _cpcv_group_ranges,
)

DEFAULT_PBO_GROUPS = DEFAULT_CPCV_GROUPS
MAX_PBO = 0.5


@dataclass(frozen=True)
class PBOResult:
    evaluated: bool
    pbo: float
    passes: bool
    n_strategies: int
    n_paths: int
    n_groups: int


def _average_ranks(values: np.ndarray) -> np.ndarray:
    """Rank 1 = lowest value. Ties receive the average rank."""
    n = len(values)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = 0.5 * ((i + 1) + (j + 1))
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def _empty(*, n_strategies: int, n_groups: int) -> PBOResult:
    return PBOResult(
        evaluated=False,
        pbo=0.0,
        passes=False,
        n_strategies=n_strategies,
        n_paths=0,
        n_groups=n_groups,
    )


def probability_of_backtest_overfitting(
    strategy_returns: Sequence[pd.Series],
    *,
    n_groups: int = DEFAULT_PBO_GROUPS,
    min_group_bars: int = MIN_CPCV_GROUP_BARS,
    periods_per_year: int = 252,
    max_pbo: float = MAX_PBO,
) -> PBOResult:
    """CSCV PBO for a set of already-scored strategy return series.

    Splits the common index into ``n_groups`` contiguous groups. Each
    combination of ``n_groups // 2`` groups is the in-sample set; the
    complement is OOS. The in-sample Sharpe winner is overfit on a path
    when its OOS relative rank is below 0.5 (rank 1 = lowest OOS Sharpe).
    """
    series = [row for row in strategy_returns if isinstance(row, pd.Series)]
    n_strategies = len(series)
    if n_strategies < 2 or n_groups < 2 or n_groups % 2 != 0:
        return _empty(n_strategies=n_strategies, n_groups=n_groups)
    frame = pd.concat(series, axis=1, join="inner")
    if frame.empty or len(frame) < n_groups * min_group_bars:
        return _empty(n_strategies=n_strategies, n_groups=n_groups)

    values = frame.to_numpy(dtype=float)
    n_obs, n_col = values.shape
    ranges = _cpcv_group_ranges(n_obs, n_groups)
    n_is = n_groups // 2
    overfit = 0
    n_paths = 0
    for combo in combinations(range(n_groups), n_is):
        is_mask = np.zeros(n_obs, dtype=bool)
        for group in combo:
            start, end = ranges[group]
            is_mask[start:end] = True
        oos_mask = ~is_mask
        if not is_mask.any() or not oos_mask.any():
            continue
        is_sharpes = np.array(
            [
                _annualized_sharpe(pd.Series(values[is_mask, j]), periods_per_year)
                for j in range(n_col)
            ],
            dtype=float,
        )
        oos_sharpes = np.array(
            [
                _annualized_sharpe(pd.Series(values[oos_mask, j]), periods_per_year)
                for j in range(n_col)
            ],
            dtype=float,
        )
        winner = int(np.argmax(is_sharpes))
        ranks = _average_ranks(oos_sharpes)
        relative = float(ranks[winner]) / float(n_col)
        n_paths += 1
        if relative < 0.5:
            overfit += 1

    if n_paths == 0:
        return _empty(n_strategies=n_strategies, n_groups=n_groups)
    pbo = overfit / n_paths
    return PBOResult(
        evaluated=True,
        pbo=float(pbo),
        passes=bool(pbo < max_pbo),
        n_strategies=n_col,
        n_paths=n_paths,
        n_groups=n_groups,
    )


def expected_cscv_paths(n_groups: int = DEFAULT_PBO_GROUPS) -> int:
    return comb(n_groups, n_groups // 2)
