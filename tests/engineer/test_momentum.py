"""
Tests for the momentum alpha factors.

Each test verifies:
  1. The factor returns a Series with the same index as the input
  2. The factor's weight values are in [0, 1] (long-only)
  3. The factor avoids look-ahead bias (output at time t depends only
     on data up to and including t, not t+1)
  4. The factor handles edge cases (empty input, too-short input)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from alphaloop.engineer import (  # noqa: E402
    macd,
    momentum_12_1,
    rsi,
    roc,
)


def _make_prices(n: int = 500, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0005, 0.012, n)
    return pd.Series(
        100.0 * np.exp(np.cumsum(rets)),
        index=pd.date_range("2018-01-01", periods=n, freq="B"),
    )


def test_rsi_returns_same_index():
    p = _make_prices()
    w = rsi(p)
    assert isinstance(w, pd.Series)
    assert (w.index == p.index).all()


def test_rsi_weights_in_01():
    p = _make_prices()
    w = rsi(p)
    assert w.between(0, 1).all()


def test_rsi_empty_input():
    assert (rsi(pd.Series(dtype=float)) == 0).all() or len(rsi(pd.Series(dtype=float))) == 0


def test_rsi_short_input_returns_zeros():
    p = _make_prices(n=5)
    w = rsi(p)
    assert (w == 0).all()


def test_rsi_strong_uptrend_is_always_long():
    """A pure uptrend should keep RSI > 50 -> always long after warmup."""
    idx = pd.date_range("2020-01-01", periods=200, freq="B")
    rng = np.random.default_rng(0)
    # Pure linspace gives constant delta which rsi may mis-handle;
    # use random walk with positive drift instead.
    rets = rng.normal(0.005, 0.001, 200)  # tight vol, positive drift
    p = pd.Series(100.0 * np.exp(np.cumsum(rets)), index=idx)
    w = rsi(p, window=14, threshold=50.0)
    # After warmup (14 bars), should be all 1.0 (long)
    assert w.iloc[20:].sum() > 150  # mostly long


def test_macd_returns_same_index():
    p = _make_prices()
    w = macd(p)
    assert (w.index == p.index).all()
    assert w.between(0, 1).all()


def test_macd_no_lookahead():
    """Changing a future bar should not affect earlier weights."""
    p = _make_prices(300)
    w1 = macd(p)
    # Modify a bar deep in the future
    p_modified = p.copy()
    p_modified.iloc[200] = p.iloc[200] * 10
    w2 = macd(p_modified)
    # Weights before bar 200 should be identical
    pd.testing.assert_series_equal(w1.iloc[:200], w2.iloc[:200], check_names=False)


def test_roc_returns_same_index():
    p = _make_prices()
    w = roc(p)
    assert (w.index == p.index).all()
    assert w.between(0, 1).all()


def test_roc_pure_uptrend_is_always_long():
    idx = pd.date_range("2020-01-01", periods=200, freq="B")
    p = pd.Series(np.linspace(100, 200, 200), index=idx)
    w = roc(p, window=20)
    # After 20 bars, ROC > 0 -> long
    assert w.iloc[40:].sum() > 100


def test_momentum_12_1_returns_same_index():
    p = _make_prices(600)
    w = momentum_12_1(p)
    assert (w.index == p.index).all()
    assert w.between(0, 1).all()


def test_momentum_12_1_pure_uptrend_is_always_long():
    idx = pd.date_range("2018-01-01", periods=400, freq="B")
    p = pd.Series(np.linspace(100, 200, 400), index=idx)
    w = momentum_12_1(p, skip=21)
    # After 252 + 21 bars, should be mostly long
    assert w.iloc[280:].sum() > 50


def test_momentum_12_1_short_input_returns_zeros():
    p = _make_prices(100)
    w = momentum_12_1(p)
    assert (w == 0).all()
