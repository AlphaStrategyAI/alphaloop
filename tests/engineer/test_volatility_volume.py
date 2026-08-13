"""
Tests for the volatility-based factors and the volume-based factor.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from alphaloop.engineer import atr_breakout, obv_slope, parkinson_hist_vol  # noqa: E402


def _make_prices(n: int = 500, seed: int = 0, drift: float = 0.0005) -> pd.Series:
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, 0.012, n)
    return pd.Series(
        100.0 * np.exp(np.cumsum(rets)),
        index=pd.date_range("2018-01-01", periods=n, freq="B"),
    )


def _make_ohlcv(prices: pd.Series, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {
            "open": prices,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices,
            "volume": rng.integers(1_000_000, 5_000_000, len(prices)).astype(float),
        },
        index=prices.index,
    )
    return df


def _ohlcv_volume(df: pd.DataFrame) -> pd.Series:
    """Extract the volume column as a Series (cast for pyright)."""
    return pd.Series(df["volume"].to_numpy(), index=df.index)


# --- atr_breakout ---


def test_atr_breakout_returns_same_index():
    p = _make_prices()
    ohlc = _make_ohlcv(p)
    w = atr_breakout(ohlc)
    assert (w.index == ohlc.index).all()
    assert w.between(0, 1).all()


def test_atr_breakout_short_input_returns_zeros():
    p = _make_prices(n=10)
    ohlc = _make_ohlcv(p)
    w = atr_breakout(ohlc)
    assert (w == 0).all()


def test_atr_breakout_can_fire():
    """Given 1500 bars of synthetic data, atr_breakout should fire at least
    once (i.e. produce non-zero weights). The earlier implementation
    had a bug where `close > rolling_high` was never true because
    rolling_high included the current bar."""
    p = _make_prices(1500)
    ohlc = _make_ohlcv(p)
    w = atr_breakout(ohlc, atr_window=14, breakout_window=50, atr_multiplier=1.5)
    assert w.sum() > 0


def test_atr_breakout_no_lookahead():
    """Modifying a future bar must not change past weights."""
    p = _make_prices(500)
    ohlc = _make_ohlcv(p)
    w1 = atr_breakout(ohlc)
    ohlc2 = ohlc.copy()
    ohlc2.iloc[400, ohlc2.columns.get_loc("close")] = ohlc.iloc[400, ohlc.columns.get_loc("close")] * 10
    w2 = atr_breakout(ohlc2)
    # Weights before bar 400 should be identical
    pd.testing.assert_series_equal(w1.iloc[:400], w2.iloc[:400], check_names=False)


# --- parkinson_hist_vol ---


def test_parkinson_returns_same_index():
    p = _make_prices()
    v = parkinson_hist_vol(p)
    assert (v.index == p.index).all()


def test_parkinson_short_input_returns_zeros():
    p = _make_prices(n=10)
    v = parkinson_hist_vol(p, window=30)
    assert (v == 0).all()


def test_parkinson_values_are_non_negative():
    p = _make_prices(500)
    v = parkinson_hist_vol(p, window=30)
    # Parkinson vol is by definition >= 0
    assert (v.dropna() >= 0).all()


def test_parkinson_constant_prices_returns_zero():
    """If the price never moves, (H/L)^2 = 0 -> vol = 0."""
    p = pd.Series(100.0, index=pd.date_range("2020-01-01", periods=100, freq="B"))
    v = parkinson_hist_vol(p, window=30)
    # After warmup, vol should be 0 everywhere
    assert v.iloc[30:].sum() == 0


# --- obv_slope ---


def test_obv_slope_returns_same_index():
    p = _make_prices()
    ohlc = _make_ohlcv(p)
    vol = _ohlcv_volume(ohlc)
    w = obv_slope(p, vol)
    assert (w.index == p.index).all()
    assert w.between(0, 1).all()


def test_obv_slope_short_input_returns_zeros():
    p = _make_prices(n=10)
    ohlc = _make_ohlcv(p)
    vol = _ohlcv_volume(ohlc)
    w = obv_slope(p, vol, window=20)
    assert (w == 0).all()


def test_obv_slope_no_lookahead():
    """Modifying a future volume bar must not change past weights."""
    p = _make_prices(500)
    ohlc = _make_ohlcv(p)
    vol = _ohlcv_volume(ohlc)
    w1 = obv_slope(p, vol, window=20)
    vol2 = vol.copy()
    vol2.iloc[400] = vol.iloc[400] * 100
    w2 = obv_slope(p, vol2, window=20)
    # Weights before bar 400 should be identical
    pd.testing.assert_series_equal(w1.iloc[:400], w2.iloc[:400], check_names=False)
