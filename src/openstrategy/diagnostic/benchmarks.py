"""
Strategy vs benchmark comparisons.

Provides three concrete comparisons for v1.0 acceptance:

  1. vs random strategy  (does your strategy beat a random one?)
  2. vs buy-and-hold     (does your strategy beat passive holding?)
  3. vs SPY buy-and-hold (does your strategy beat the S&P 500?)

Each comparison returns a simple, actionable result: p-value, win
probability, or Sharpe ratio gap.

Usage:
    from openstrategy.diagnostic import vs_random, vs_buy_hold, vs_spy_buyhold
    from openstrategy.data import YahooFinanceSource
    import pandas as pd

    source = YahooFinanceSource()
    my_returns = pd.Series(...)  # daily returns of your strategy
    spy_prices = source.get_data("SPY", period="5y")["close"]

    rand = vs_random(my_returns, n_simulations=1000)
    bh = vs_buy_hold(my_returns, buy_hold_prices=...)
    spy = vs_spy_buyhold(my_returns, spy_prices=spy_prices)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


# --- Helpers ---


def _annualized_sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    if returns.empty or returns.std() == 0:
        return 0.0
    return float(returns.mean() / returns.std() * np.sqrt(periods_per_year))


def _returns_from_prices(prices: pd.Series) -> pd.Series:
    return prices.pct_change().dropna()


def _align(returns_a: pd.Series, returns_b: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Inner-join two return series on date index."""
    a = returns_a.copy()
    b = returns_b.copy()
    if not isinstance(a.index, pd.DatetimeIndex):
        a.index = pd.to_datetime(a.index)
    if not isinstance(b.index, pd.DatetimeIndex):
        b.index = pd.to_datetime(b.index)
    a.name = "a"
    b.name = "b"
    joined: pd.DataFrame = pd.concat([a, b], axis=1, join="inner").dropna()
    if joined.empty:
        return joined["a"], joined["b"]
    return joined["a"], joined["b"]


# --- Result types ---


@dataclass
class VsRandomResult:
    strategy_sharpe: float
    random_sharpe_mean: float
    random_sharpe_std: float
    p_value: float  # fraction of random strategies that beat yours
    passes: bool  # your strategy's max-DD is BETTER than random

    def summary(self) -> str:
        verdict = "PASS" if self.passes else "FAIL"
        return (
            f"vs Random verdict: {verdict}\n"
            f"  Your Sharpe:           {self.strategy_sharpe:.3f}\n"
            f"  Random mean (n=1000):  {self.random_sharpe_mean:.3f}\n"
            f"  Random std:            {self.random_sharpe_std:.3f}\n"
            f"  P(random SR > you):   {self.p_value:.3f}"
        )


@dataclass
class VsBuyHoldResult:
    strategy_sharpe: float
    buy_hold_sharpe: float
    sharpe_gap: float
    strategy_total_return: float
    buy_hold_total_return: float
    passes: bool

    def summary(self) -> str:
        verdict = "PASS" if self.passes else "FAIL"
        return (
            f"vs Buy & Hold verdict: {verdict}\n"
            f"  Your Sharpe:        {self.strategy_sharpe:.3f}\n"
            f"  Buy & Hold Sharpe:  {self.buy_hold_sharpe:.3f}\n"
            f"  Sharpe gap:         {self.sharpe_gap:+.3f}\n"
            f"  Your total return:  {self.strategy_total_return:+.3%}\n"
            f"  B&H total return:   {self.buy_hold_total_return:+.3%}"
        )


@dataclass
class VsSpyBuyHoldResult:
    strategy_sharpe: float
    spy_sharpe: float
    sharpe_gap: float
    strategy_total_return: float
    spy_total_return: float
    passes: bool

    def summary(self) -> str:
        verdict = "PASS" if self.passes else "FAIL"
        return (
            f"vs SPY Buy & Hold verdict: {verdict}\n"
            f"  Your Sharpe:        {self.strategy_sharpe:.3f}\n"
            f"  SPY Sharpe:         {self.spy_sharpe:.3f}\n"
            f"  Sharpe gap:         {self.sharpe_gap:+.3f}\n"
            f"  Your total return:  {self.strategy_total_return:+.3%}\n"
            f"  SPY total return:   {self.spy_total_return:+.3%}"
        )


# --- Public API ---


def _max_drawdown(returns: pd.Series) -> float:
    """Max drawdown of a return series (negative number, e.g. -0.2 = 20% drawdown)."""
    if returns.empty:
        return 0.0
    cum = (1.0 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    return float(dd.min())


def vs_random(
    strategy_returns: pd.Series,
    n_simulations: int = 1000,
    block_size: int = 21,
    seed: int = 42,
    periods_per_year: int = 252,
) -> VsRandomResult:
    """Compare your strategy's risk-adjusted return to n block-shuffled baselines.

    Simple Sharpe-ratio comparison is misleading because block-shuffling
    preserves the marginal return distribution, so the shuffled series
    has nearly the same Sharpe as the original. We use **max drawdown**
    as the test statistic: a real trend-following / momentum strategy
    has a much shallower max drawdown than a randomly shuffled version
    of its own returns (because the shuffled version has no idea when
    to cut losses).

    Args:
        strategy_returns: Daily return series of your strategy.
        n_simulations: Number of block-shuffled baselines to draw.
        block_size: Block length in bars (default 21 ~ 1 month of
            trading days). Larger blocks preserve more serial
            structure; smaller blocks converge to pure shuffle.
        seed: RNG seed for reproducibility.
        periods_per_year: For annualizing Sharpe.

    Returns:
        VsRandomResult with p_value = fraction of random baselines
        whose Sharpe exceeds yours, AND `passes=True` iff your
        max drawdown is *better* (less negative) than the median
        random baseline.
    """
    if n_simulations < 1:
        raise ValueError(f"n_simulations must be >= 1, got {n_simulations}")
    if block_size < 1:
        raise ValueError(f"block_size must be >= 1, got {block_size}")
    if strategy_returns.empty:
        raise ValueError("strategy_returns is empty")

    rng = np.random.default_rng(seed)
    strategy_sharpe = _annualized_sharpe(strategy_returns, periods_per_year)
    strategy_max_dd = _max_drawdown(strategy_returns)

    rets = strategy_returns.to_numpy()
    n = len(rets)
    if n < block_size * 2:
        block_size = 1

    random_sharpes = np.empty(n_simulations)
    random_max_dds = np.empty(n_simulations)
    for i in range(n_simulations):
        n_blocks = n // block_size
        usable = n_blocks * block_size
        blocks = rets[:usable].reshape(n_blocks, block_size)
        block_order = rng.permutation(n_blocks)
        shuffled = blocks[block_order].ravel()
        if usable < n:
            shuffled = np.concatenate([shuffled, rets[usable:]])
        shuffled_s = pd.Series(shuffled)
        random_sharpes[i] = _annualized_sharpe(shuffled_s, periods_per_year)
        random_max_dds[i] = _max_drawdown(shuffled_s)

    p_value = float((random_sharpes >= strategy_sharpe).sum() / n_simulations)
    # A strategy "beats random" if its max drawdown is shallower
    # (less negative) than the median random baseline. This is the
    # right tail-comparison: random can have huge drawdowns, a real
    # strategy cannot.
    passes = bool(strategy_max_dd > np.median(random_max_dds))
    return VsRandomResult(
        strategy_sharpe=strategy_sharpe,
        random_sharpe_mean=float(random_sharpes.mean()),
        random_sharpe_std=float(random_sharpes.std()),
        p_value=p_value,
        passes=passes,
    )


def vs_buy_hold(
    strategy_returns: pd.Series,
    buy_hold_prices: pd.Series,
    periods_per_year: int = 252,
) -> VsBuyHoldResult:
    """Compare your strategy to passive buy-and-hold of the same instrument.

    Pass the same underlying price series you used for the strategy.
    """
    if strategy_returns.empty or buy_hold_prices.empty:
        raise ValueError("Both series must be non-empty")

    bh_returns = _returns_from_prices(buy_hold_prices)
    sa, ba = _align(strategy_returns, bh_returns)
    if len(sa) < 5:
        raise ValueError(
            f"Need >= 5 overlapping bars, got {len(sa)}"
        )

    s_sharpe = _annualized_sharpe(sa, periods_per_year)
    b_sharpe = _annualized_sharpe(ba, periods_per_year)
    s_total = float((1.0 + sa).prod() - 1.0)
    b_total = float((1.0 + ba).prod() - 1.0)
    return VsBuyHoldResult(
        strategy_sharpe=s_sharpe,
        buy_hold_sharpe=b_sharpe,
        sharpe_gap=s_sharpe - b_sharpe,
        strategy_total_return=s_total,
        buy_hold_total_return=b_total,
        passes=s_sharpe > b_sharpe,
    )


def vs_spy_buyhold(
    strategy_returns: pd.Series,
    spy_prices: pd.Series,
    periods_per_year: int = 252,
) -> VsSpyBuyHoldResult:
    """Compare your strategy to SPY buy-and-hold over the same window.

    The hardest benchmark: most individual strategies do not beat SPY
    after fees and slippage. This is the v1.0 acceptance criterion #6.
    """
    if strategy_returns.empty or spy_prices.empty:
        raise ValueError("Both series must be non-empty")

    spy_returns = _returns_from_prices(spy_prices)
    sa, spa = _align(strategy_returns, spy_returns)
    if len(sa) < 5:
        raise ValueError(
            f"Need >= 5 overlapping bars, got {len(sa)}"
        )

    s_sharpe = _annualized_sharpe(sa, periods_per_year)
    spy_sharpe = _annualized_sharpe(spa, periods_per_year)
    s_total = float((1.0 + sa).prod() - 1.0)
    spy_total = float((1.0 + spa).prod() - 1.0)
    return VsSpyBuyHoldResult(
        strategy_sharpe=s_sharpe,
        spy_sharpe=spy_sharpe,
        sharpe_gap=s_sharpe - spy_sharpe,
        strategy_total_return=s_total,
        spy_total_return=spy_total,
        passes=s_sharpe > spy_sharpe,
    )
