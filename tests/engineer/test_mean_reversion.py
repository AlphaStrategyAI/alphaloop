"""
Tests for the mean-reversion factors.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from alphaloop.engineer import (  # noqa: E402
    bollinger_zscore,
    ohlr_4_pct,
    pairs_spread,
)


def _make_prices(n: int = 500, seed: int = 0, drift: float = 0.0) -> pd.Series:
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, 0.012, n)
    return pd.Series(
        100.0 * np.exp(np.cumsum(rets)),
        index=pd.date_range("2018-01-01", periods=n, freq="B"),
    )


def _make_ohlc(prices: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices,
        },
        index=prices.index,
    )


def test_bollinger_returns_same_index():
    p = _make_prices()
    w = bollinger_zscore(p)
    assert (w.index == p.index).all()
    assert w.between(0, 1).all()


def test_bollinger_short_input_returns_zeros():
    p = _make_prices(n=10)
    w = bollinger_zscore(p, window=20)
    assert (w == 0).all()


def test_bollinger_long_after_a_big_drop():
    """A single big down bar should trigger a long signal (price below MA - 1.5 std)."""
    idx = pd.date_range("2020-01-01", periods=200, freq="B")
    p = pd.Series(100 + np.cumsum(np.random.default_rng(0).normal(0, 0.005, 200)), index=idx)
    p.iloc[150] = p.iloc[150] * 0.85  # 15% drop in one bar
    w = bollinger_zscore(p, window=20, num_std=1.5)
    # At bar 150, weight should be 1 (price way below lower band)
    assert w.iloc[151] == 1.0  # shifted by 1, so the long comes at bar 151


def test_bollinger_invert_false_is_momentum():
    p = _make_prices()
    w_inv = bollinger_zscore(p, invert=True)
    w_mom = bollinger_zscore(p, invert=False)
    # The two should be (almost) disjoint in their long signals
    both_long = (w_inv > 0) & (w_mom > 0)
    assert both_long.sum() < min((w_inv > 0).sum(), (w_mom > 0).sum())


def test_bollinger_short_window_weights_in_01():
    p = _make_prices()
    w = bollinger_zscore(p, window=10, num_std=1.5)
    assert w.between(0, 1).all()


def test_ohlr_returns_same_index():
    p = _make_prices()
    ohlc = _make_ohlc(p)
    w = ohlr_4_pct(ohlc)
    assert (w.index == ohlc.index).all()
    assert w.between(0, 1).all()


def test_ohlr_short_input_returns_zeros():
    p = _make_prices(n=10)
    ohlc = _make_ohlc(p)
    w = ohlr_4_pct(ohlc)
    assert (w == 0).all()


def test_ohlr_pure_downtrend_signals_long():
    """In a pure downtrend, %R should be near -100 -> long signal."""
    idx = pd.date_range("2020-01-01", periods=200, freq="B")
    p = pd.Series(np.linspace(200, 100, 200), index=idx)
    ohlc = _make_ohlc(p)
    w = ohlr_4_pct(ohlc)
    # After warmup, weight should be 1 most of the time
    assert w.iloc[20:].sum() > 100


def test_ohlr_period_changes_signal():
    p = _make_prices(n=80, seed=1)
    ohlc = _make_ohlc(p)
    fast = ohlr_4_pct(ohlc, period=10, threshold=80.0)
    slow = ohlr_4_pct(ohlc, period=21, threshold=80.0)
    assert fast.between(0, 1).all()
    assert slow.between(0, 1).all()
    assert not fast.equals(slow)


def test_ohlr_oversold_threshold_longs_downtrend():
    idx = pd.date_range("2020-01-01", periods=200, freq="B")
    p = pd.Series(np.linspace(200, 100, 200), index=idx)
    w = ohlr_4_pct(_make_ohlc(p), period=14, threshold=80.0)
    assert w.iloc[20:].sum() > 100


def test_pairs_spread_returns_same_index():
    p1 = _make_prices(seed=1)
    p2 = _make_prices(seed=2)
    w = pairs_spread(p1, p2)
    assert (w.index == p1.index).all()
    assert w.between(0, 1).all()


def test_pairs_spread_short_input_returns_zeros():
    p1 = _make_prices(n=10)
    p2 = _make_prices(seed=2, n=10)
    w = pairs_spread(p1, p2, window=60)
    assert (w == 0).all()


def test_pairs_spread_different_index_handles_inner_join():
    """When the two series have different indices, we use the inner join."""
    idx1 = pd.date_range("2018-01-01", periods=300, freq="B")
    idx2 = pd.date_range("2019-01-01", periods=300, freq="B")
    # Use the SAME random walk for both, then add different noise.
    # This creates mean-reverting spread behavior.
    rng = np.random.default_rng(0)
    common = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, 600)))
    p1 = pd.Series(common[:300], index=idx1)
    p2 = pd.Series(common[300:] * (1.0 + rng.normal(0, 0.001, 300)), index=idx2)
    w = pairs_spread(p1, p2, window=20)  # window < 39 overlap bars
    # Output index should match p1
    assert (w.index == p1.index).all()
    # Should have some non-zero weights on the overlapping window
    assert w.sum() > 0


def test_pairs_window_changes_signal():
    p1 = _make_prices(n=400, seed=1)
    p2 = _make_prices(n=400, seed=2)
    short = pairs_spread(p1, p2, window=126)
    long = pairs_spread(p1, p2, window=252)
    assert short.between(0, 1).all()
    assert long.between(0, 1).all()
    assert not short.equals(long)
