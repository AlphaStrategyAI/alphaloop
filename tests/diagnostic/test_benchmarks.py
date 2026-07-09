"""
Tests for the benchmark comparisons: vs_random, vs_buy_hold, vs_spy_buyhold.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from openstrategy.diagnostic import (  # noqa: E402
    vs_buy_hold,
    vs_random,
    vs_spy_buyhold,
)


def _make_returns(n: int = 500, seed: int = 0, drift: float = 0.0005) -> pd.Series:
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, 0.01, n)
    return pd.Series(rets, index=pd.date_range("2020-01-01", periods=n, freq="B"))


def _make_prices(n: int = 500, seed: int = 0, drift: float = 0.0005) -> pd.Series:
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, 0.01, n)
    prices = 100.0 * np.exp(np.cumsum(rets))
    return pd.Series(prices, index=pd.date_range("2020-01-01", periods=n, freq="B"))


# ----- vs_random -----


def test_vs_random_rejects_zero_simulations():
    rets = _make_returns()
    with pytest.raises(ValueError, match="n_simulations must be >= 1"):
        vs_random(rets, n_simulations=0)


def test_vs_random_rejects_empty():
    with pytest.raises(ValueError, match="strategy_returns is empty"):
        vs_random(pd.Series([], dtype=float))


def test_vs_random_block_bootstrap_preserves_sharpe_distribution():
    """Block shuffle keeps mean Sharpe ~ original (preserves marginal)."""
    rets = _make_returns(500, drift=0.001, seed=0)
    result = vs_random(rets, n_simulations=200, block_size=21, seed=42)
    # With block bootstrap, the *mean* of random Sharpes should be
    # close to the original strategy's Sharpe.
    assert abs(result.random_sharpe_mean - result.strategy_sharpe) < 0.3


def test_vs_random_returns_result_with_summary():
    rets = _make_returns(300)
    result = vs_random(rets, n_simulations=50)
    s = result.summary()
    assert "vs Random verdict" in s
    assert "Your Sharpe" in s


def test_vs_random_seed_is_reproducible():
    rets = _make_returns(300, seed=10)
    r1 = vs_random(rets, n_simulations=100, seed=42)
    r2 = vs_random(rets, n_simulations=100, seed=42)
    assert r1.p_value == r2.p_value
    assert r1.random_sharpe_mean == r2.random_sharpe_mean


def test_vs_random_failing_strategy_actually_fails():
    """A negative-drift series should fail vs_random (max_dd just as bad)."""
    rets = _make_returns(500, drift=-0.001, seed=0)  # losing
    result = vs_random(rets, n_simulations=200, block_size=21, seed=42)
    assert not result.passes  # no edge to extract


def test_vs_random_strong_signal_passes():
    """A clearly trending series should pass vs_random.

    With a strong drift (0.5% per day) and 500 bars, the strategy's
    max drawdown is shallow (always climbing). The block-shuffled
    baselines, even with the same marginal distribution, will have
    large max drawdowns because they have no idea when to stop.
    Therefore the strategy's max_dd should be BETTER than the median
    random baseline.
    """
    rets = _make_returns(500, drift=0.005, seed=99)  # strong upward drift
    result = vs_random(rets, n_simulations=200, block_size=21, seed=42)
    assert result.passes
    # Sanity: even Sharpe is comparable, but max_dd is much better
    assert result.strategy_sharpe > result.random_sharpe_mean - 1.0  # not a strict test


# ----- vs_buy_hold -----


def test_vs_buy_hold_better_strategy_passes():
    """A strategy with higher Sharpe than buy & hold should pass."""
    rets = _make_returns(500, drift=0.002, seed=0)
    prices = _make_prices(500, drift=0.0001, seed=1)  # buy & hold with much lower drift
    result = vs_buy_hold(rets, prices)
    assert result.passes
    assert result.strategy_sharpe > result.buy_hold_sharpe
    assert result.sharpe_gap > 0


def test_vs_buy_hold_worse_strategy_fails():
    """A strategy worse than buy & hold should fail."""
    rets = _make_returns(500, drift=-0.001, seed=0)  # losing strategy
    prices = _make_prices(500, drift=0.001, seed=1)
    result = vs_buy_hold(rets, prices)
    assert not result.passes
    assert result.strategy_sharpe < result.buy_hold_sharpe


def test_vs_buy_hold_rejects_empty_inputs():
    with pytest.raises(ValueError, match="non-empty"):
        vs_buy_hold(pd.Series([], dtype=float), _make_prices())


def test_vs_buy_hold_rejects_too_little_overlap():
    """If price series has < 5 overlapping bars, raise."""
    rets = pd.Series([0.01] * 100, index=pd.date_range("2020-01-01", periods=100, freq="B"))
    prices = pd.Series([100.0] * 100, index=pd.date_range("2025-01-01", periods=100, freq="B"))
    with pytest.raises(ValueError, match="overlapping bars"):
        vs_buy_hold(rets, prices)


# ----- vs_spy_buyhold -----


def test_vs_spy_buyhold_strong_strategy_passes():
    """A strategy with much higher Sharpe than SPY should pass."""
    rets = _make_returns(500, drift=0.002, seed=0)  # strong
    spy = _make_prices(500, drift=0.0003, seed=42)  # market-level
    result = vs_spy_buyhold(rets, spy)
    assert result.passes
    assert result.strategy_sharpe > result.spy_sharpe
    assert result.sharpe_gap > 0


def test_vs_spy_buyhold_weak_strategy_fails():
    """A strategy with low Sharpe should fail vs SPY."""
    rets = _make_returns(500, drift=-0.0005, seed=0)
    spy = _make_prices(500, drift=0.0008, seed=42)
    result = vs_spy_buyhold(rets, spy)
    assert not result.passes
    assert result.strategy_sharpe < result.spy_sharpe


def test_vs_spy_buyhold_summary_contains_spy():
    rets = _make_returns(300, seed=0)
    spy = _make_prices(300, seed=42)
    result = vs_spy_buyhold(rets, spy)
    s = result.summary()
    assert "SPY" in s
    assert "Your Sharpe" in s


def test_vs_spy_buyhold_rejects_empty():
    with pytest.raises(ValueError, match="non-empty"):
        vs_spy_buyhold(pd.Series([], dtype=float), _make_prices())


# ----- Integration: all three on the same series -----


def test_three_benchmarks_consistent():
    """All three benchmarks should run on the same returns and price series."""
    rets = _make_returns(500, drift=0.001, seed=42)
    prices = _make_prices(500, drift=0.0008, seed=43)
    spy = _make_prices(500, drift=0.0008, seed=44)

    r_rand = vs_random(rets, n_simulations=100, block_size=21)
    r_bh = vs_buy_hold(rets, prices)
    r_spy = vs_spy_buyhold(rets, spy)

    # All should return valid result objects
    assert 0.0 <= r_rand.p_value <= 1.0
    assert r_bh.sharpe_gap == r_bh.strategy_sharpe - r_bh.buy_hold_sharpe
    assert r_spy.sharpe_gap == r_spy.strategy_sharpe - r_spy.spy_sharpe
