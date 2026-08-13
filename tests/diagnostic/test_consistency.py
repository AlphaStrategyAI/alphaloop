"""
Tests for data_source_consistency().
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from alphaloop.diagnostic import (  # noqa: E402
    ConsistencyResult,
    data_source_consistency,
)


def _make_ohlcv(prices: np.ndarray, start: str = "2024-01-01") -> pd.DataFrame:
    """Wrap a price array into a minimal OHLCV DataFrame."""
    n = len(prices)
    idx = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.full(n, 1_000_000),
        },
        index=idx,
    )


def test_identical_sources_pass():
    """Two identical price series should obviously pass consistency."""
    prices = np.cumprod(1.0 + np.random.default_rng(0).normal(0.001, 0.01, 252))
    a = _make_ohlcv(prices)
    b = _make_ohlcv(prices)
    result = data_source_consistency(a, b, symbol="AAPL")
    assert result.passes
    assert result.mean_rel_error == pytest.approx(0.0, abs=1e-12)
    assert result.return_corr == pytest.approx(1.0, abs=1e-9)


def test_small_noise_still_passes():
    """Tiny noise (< 0.1%) should not break the 5% threshold."""
    prices = np.cumprod(1.0 + np.random.default_rng(1).normal(0.001, 0.01, 500))
    a = _make_ohlcv(prices)
    b_prices = prices * np.random.default_rng(2).uniform(0.999, 1.001, len(prices))
    b = _make_ohlcv(b_prices)
    result = data_source_consistency(a, b, symbol="AAPL")
    assert result.passes
    assert result.mean_rel_error < 0.01


def test_large_disagreement_fails():
    """5%+ systematic disagreement should fail the v1.0 threshold."""
    prices = np.cumprod(1.0 + np.random.default_rng(3).normal(0.001, 0.01, 500))
    a = _make_ohlcv(prices)
    b_prices = prices * 1.10  # 10% bias
    b = _make_ohlcv(b_prices)
    result = data_source_consistency(a, b, symbol="AAPL")
    assert not result.passes
    assert result.mean_rel_error > 0.05


def test_missing_close_column_raises():
    a = pd.DataFrame({"open": [1, 2], "high": [2, 3]})
    b = pd.DataFrame({"open": [1, 2], "high": [2, 3]})
    with pytest.raises(ValueError, match="'close'"):
        data_source_consistency(a, b)


def test_no_overlap_returns_failing_result():
    """Disjoint date ranges -> 0 overlap -> fail."""
    idx_a = pd.date_range("2020-01-01", periods=100, freq="B")
    idx_b = pd.date_range("2025-01-01", periods=100, freq="B")
    a = pd.DataFrame({"close": np.ones(100)}, index=idx_a)
    b = pd.DataFrame({"close": np.ones(100)}, index=idx_b)
    result = data_source_consistency(a, b, symbol="AAPL")
    assert result.n_overlap < 5
    assert not result.passes


def test_inner_join_aligns_correctly():
    """Inner-join should only use overlapping dates."""
    # Use a single shared 300-bar index, then truncate each side
    # differently. The overlap is determined by the business-day
    # calendar of the index, not raw length.
    full_idx = pd.date_range("2024-01-01", periods=300, freq="B")
    rng = np.random.default_rng(4)
    # Use the SAME 300 returns for both sides, then truncate.
    # a = first 200 bars, b = last 200 bars -> overlap is 100 bars
    # of identical data.
    all_rets = rng.normal(0.001, 0.01, 300)
    a = pd.DataFrame(
        {"close": 100.0 * np.cumprod(1.0 + all_rets[:200])},
        index=full_idx[:200],
    )
    b = pd.DataFrame(
        {"close": 100.0 * np.cumprod(1.0 + all_rets[100:])},
        index=full_idx[100:],
    )
    result = data_source_consistency(a, b, symbol="AAPL")
    # Overlap is the intersection: full_idx[100:200] = 100 bars
    assert result.n_overlap == 100
    assert result.return_corr > 0.99


def test_summary_format():
    prices = np.cumprod(1.0 + np.random.default_rng(5).normal(0.001, 0.01, 252))
    a = _make_ohlcv(prices)
    b = _make_ohlcv(prices)
    result = data_source_consistency(a, b, symbol="AAPL")
    s = result.summary()
    assert "Cross-source consistency verdict" in s
    assert "AAPL" in s


def test_nan_in_one_source_dropped():
    prices = np.cumprod(1.0 + np.random.default_rng(6).normal(0.001, 0.01, 252))
    a = _make_ohlcv(prices)
    b = _make_ohlcv(prices)
    b.iloc[10, b.columns.get_loc("close")] = np.nan
    result = data_source_consistency(a, b, symbol="AAPL")
    # Should still work, just with n_overlap reduced
    assert result.n_overlap == 251


def test_p95_rel_error_catches_tail_events():
    """Even if mean error is small, p95 should catch large single-bar disagreements.

    To make p95 > 0 reliably, we need > 5% of the bars to be off
    (p95 is the 95th percentile). We use 10% of bars with 5% bias.
    """
    rng = np.random.default_rng(7)
    prices = np.cumprod(1.0 + rng.normal(0.001, 0.01, 500))
    a = _make_ohlcv(prices)
    b_prices = prices.copy()
    # Make 50 bars (10%) systematically 5% off
    off_idx = rng.choice(500, size=50, replace=False)
    b_prices[off_idx] = b_prices[off_idx] * 1.05
    b = _make_ohlcv(b_prices)
    result = data_source_consistency(a, b, symbol="AAPL")
    assert result.p95_rel_error > 0.02  # at least 2% on the 95th percentile
    assert not result.passes  # the 5% bias should fail the v1.0 threshold
