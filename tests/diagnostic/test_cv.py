"""
Tests for walk_forward_cv().
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from alphaloop.diagnostic import (  # noqa: E402
    WalkForwardFold,
    WalkForwardResult,
    walk_forward_cv,
)


def _make_prices(n: int = 1000, seed: int = 0, drift: float = 0.0003) -> pd.Series:
    """Random walk with a positive drift."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, 0.01, n)
    prices = 100.0 * np.exp(np.cumsum(rets))
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series(prices, index=idx)


def _buy_and_hold(prices: pd.Series) -> pd.Series:
    return pd.Series(1.0, index=prices.index)


def test_walk_forward_returns_result_dataclass():
    prices = _make_prices(500)
    result = walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=50, step_size=50)
    assert isinstance(result, WalkForwardResult)
    assert result.n_folds >= 1


def test_walk_forward_folds_have_correct_types():
    prices = _make_prices(500)
    result = walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=50)
    for f in result.folds:
        assert isinstance(f, WalkForwardFold)
        assert isinstance(f.oos_sharpe, float)


def test_walk_forward_default_step_equals_test_size():
    """step_size=None defaults to test_size (non-overlapping test windows)."""
    prices = _make_prices(1000)
    result = walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=63, step_size=None)
    # The number of folds with non-overlapping windows is roughly
    # (n - train_size) / test_size.
    expected = (1000 - 200) // 63
    assert result.n_folds == expected


def test_walk_forward_buy_and_hold_is_profitable():
    """With positive drift, buy-and-hold should have positive OOS Sharpe on average."""
    prices = _make_prices(1000, drift=0.001)
    result = walk_forward_cv(prices, _buy_and_hold, train_size=252, test_size=63)
    assert result.oos_sharpe_mean > 0
    assert result.passes


def test_walk_forward_rejects_short_series():
    prices = _make_prices(100)
    with pytest.raises(ValueError, match="Need at least"):
        walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=50)


def test_walk_forward_rejects_non_series():
    with pytest.raises(TypeError, match="must be a pandas Series"):
        walk_forward_cv([1, 2, 3], _buy_and_hold, train_size=2, test_size=1)


def test_walk_forward_empty_result_on_impossible_params():
    """train_size+test_size > n but somehow pass — should produce 0 folds."""
    prices = _make_prices(10)
    with pytest.raises(ValueError):
        walk_forward_cv(prices, _buy_and_hold, train_size=20, test_size=5)


def test_walk_forward_step_smaller_than_test_creates_overlap():
    """step_size < test_size -> overlapping test windows, more folds."""
    prices = _make_prices(1000)
    r_disjoint = walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=63, step_size=63)
    r_overlap = walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=63, step_size=21)
    assert r_overlap.n_folds >= r_disjoint.n_folds


def test_walk_forward_negative_drift_fails():
    """With negative drift, buy-and-hold OOS Sharpe should be negative."""
    prices = _make_prices(1000, drift=-0.001)
    result = walk_forward_cv(prices, _buy_and_hold, train_size=252, test_size=63)
    assert result.oos_sharpe_mean < 0
    assert not result.passes


def test_walk_forward_summary_is_string():
    prices = _make_prices(500)
    result = walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=63)
    s = result.summary()
    assert isinstance(s, str)
    assert "Walk-Forward CV verdict" in s
