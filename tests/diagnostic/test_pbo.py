"""Tests for probability_of_backtest_overfitting()."""
from __future__ import annotations

from math import comb

import numpy as np
import pandas as pd

from alphaloop.diagnostic.pbo import probability_of_backtest_overfitting


def _idx(n: int = 180) -> pd.DatetimeIndex:
    return pd.bdate_range("2020-01-01", periods=n)


def test_pbo_not_evaluated_for_one_strategy():
    one = pd.Series(0.001, index=_idx())
    result = probability_of_backtest_overfitting([one])
    assert result.evaluated is False
    assert result.n_paths == 0
    assert result.passes is False


def test_pbo_not_evaluated_when_series_is_short():
    idx = _idx(80)
    a = pd.Series(0.001, index=idx)
    b = pd.Series(0.002, index=idx)
    result = probability_of_backtest_overfitting([a, b])
    assert result.evaluated is False


def test_pbo_identical_series_passes():
    idx = _idx(180)
    a = pd.Series(0.001, index=idx)
    result = probability_of_backtest_overfitting([a, a.copy(), a.copy()])
    assert result.evaluated is True
    assert result.n_groups == 6
    assert result.n_paths == comb(6, 3)
    assert result.n_strategies == 3
    assert result.pbo < 0.5
    assert result.passes is True


def test_pbo_fails_when_is_winner_is_oos_loser():
    idx = _idx(180)
    n = len(idx)
    mid = n // 2
    early = np.concatenate([np.full(mid, 0.02), np.full(n - mid, -0.02)])
    late = np.concatenate([np.full(mid, -0.02), np.full(n - mid, 0.02)])
    flat = np.full(n, 0.0)
    result = probability_of_backtest_overfitting(
        [
            pd.Series(early, index=idx),
            pd.Series(flat, index=idx),
            pd.Series(late, index=idx),
        ]
    )
    assert result.evaluated is True
    assert result.pbo >= 0.5
    assert result.passes is False
