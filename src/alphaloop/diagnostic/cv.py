"""
Walk-Forward Cross-Validation for time-series backtests.

Walk-forward CV is the standard approach to estimate out-of-sample
performance for a trading strategy. It repeatedly:
  1. Train on a rolling window of N bars
  2. Test on the next M bars
  3. Roll the window forward by S bars

This avoids look-ahead bias that a single train/test split suffers from
and gives a distribution of out-of-sample Sharpe ratios, not just one
point estimate.

Usage:
    from alphaloop.diagnostic import walk_forward_cv, WalkForwardResult

    # df must have a 'close' column and a DatetimeIndex
    result = walk_forward_cv(
        prices=df["close"],
        strategy_fn=my_strategy_signal,
        train_size=252,
        test_size=63,
        step_size=21,
    )
    print(result.oos_sharpe_mean, result.oos_sharpe_std)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

import numpy as np
import pandas as pd


@dataclass
class WalkForwardFold:
    """One fold of a walk-forward CV run."""

    fold_id: int
    train_start: "Any"  # pd.Timestamp (Pyright can't infer Series.index type)
    train_end: "Any"
    test_start: "Any"
    test_end: "Any"
    train_sharpe: float
    oos_sharpe: float  # out-of-sample
    oos_return: float
    oos_max_drawdown: float


@dataclass
class WalkForwardResult:
    """Aggregate result of a walk-forward CV run."""

    folds: List[WalkForwardFold]
    oos_sharpe_mean: float
    oos_sharpe_std: float
    oos_sharpe_median: float
    oos_return_mean: float
    n_folds: int
    passes: bool  # mean OOS Sharpe > 0

    def summary(self) -> str:
        verdict = "PASS" if self.passes else "FAIL"
        return (
            f"Walk-Forward CV verdict: {verdict}\n"
            f"  N folds:           {self.n_folds}\n"
            f"  OOS Sharpe mean:   {self.oos_sharpe_mean:.3f}\n"
            f"  OOS Sharpe std:    {self.oos_sharpe_std:.3f}\n"
            f"  OOS Sharpe median: {self.oos_sharpe_median:.3f}\n"
            f"  OOS return mean:   {self.oos_return_mean:.3%}"
        )


def _annualized_sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    """Annualized Sharpe ratio (no risk-free rate)."""
    if returns.empty or returns.std() == 0:
        return 0.0
    return float(returns.mean() / returns.std() * np.sqrt(periods_per_year))


def _max_drawdown(returns: pd.Series) -> float:
    """Max drawdown of a return series (negative number)."""
    if returns.empty:
        return 0.0
    cum = (1.0 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    return float(dd.min())


def walk_forward_cv(
    prices: pd.Series,
    strategy_fn: Callable[[pd.Series], pd.Series],
    train_size: int = 252,
    test_size: int = 63,
    step_size: Optional[int] = None,
    periods_per_year: int = 252,
    min_oos_sharpe: float = 0.0,
) -> WalkForwardResult:
    """Walk-forward cross-validation.

    Args:
        prices: Price series with a DatetimeIndex.
        strategy_fn: Function that takes a price series and returns
            a series of position weights or signals (same length).
            For convenience, see `alphaloop.diagnostic.helpers`.
        train_size: Number of bars in the training window.
        test_size: Number of bars in the test (out-of-sample) window.
        step_size: How many bars to roll forward each fold. Defaults
            to `test_size` (non-overlapping test windows).
        periods_per_year: For annualizing Sharpe. Default 252 (daily).
        min_oos_sharpe: Threshold for `result.passes` (default 0.0,
            i.e. mean OOS Sharpe must be positive).

    Returns:
        WalkForwardResult with per-fold details and aggregate stats.
    """
    if step_size is None:
        step_size = test_size
    if not isinstance(prices, pd.Series):
        raise TypeError(f"prices must be a pandas Series, got {type(prices)}")
    if len(prices) < train_size + test_size:
        raise ValueError(
            f"Need at least train_size+test_size = {train_size + test_size} bars, "
            f"got {len(prices)}"
        )

    folds: List[WalkForwardFold] = []
    fold_id = 0
    i = 0
    while i + train_size + test_size <= len(prices):
        train_idx = prices.index[i : i + train_size]
        test_idx = prices.index[i + train_size : i + train_size + test_size]

        # Coerce index labels to Timestamp for the dataclass type hint.
        idx = prices.index
        train_start = pd.Timestamp(idx[i])
        train_end = pd.Timestamp(idx[i + train_size - 1])
        test_start = pd.Timestamp(idx[i + train_size])
        test_end = pd.Timestamp(idx[i + train_size + test_size - 1])

        train_prices = prices.iloc[i : i + train_size]
        test_prices = prices.iloc[i + train_size : i + train_size + test_size]

        train_weights = strategy_fn(train_prices)
        train_returns = (train_prices.pct_change().fillna(0.0) * train_weights.shift(1).fillna(0.0))

        test_weights = strategy_fn(test_prices)
        test_returns = (test_prices.pct_change().fillna(0.0) * test_weights.shift(1).fillna(0.0))

        folds.append(
            WalkForwardFold(
                fold_id=fold_id,
                train_start=train_idx[0],
                train_end=train_idx[-1],
                test_start=test_idx[0],
                test_end=test_idx[-1],
                train_sharpe=_annualized_sharpe(train_returns, periods_per_year),
                oos_sharpe=_annualized_sharpe(test_returns, periods_per_year),
                oos_return=float((1.0 + test_returns).prod() - 1.0),
                oos_max_drawdown=_max_drawdown(test_returns),
            )
        )

        fold_id += 1
        i += step_size

    if not folds:
        return WalkForwardResult(
            folds=[],
            oos_sharpe_mean=0.0,
            oos_sharpe_std=0.0,
            oos_sharpe_median=0.0,
            oos_return_mean=0.0,
            n_folds=0,
            passes=False,
        )

    oos_sharpes = np.array([f.oos_sharpe for f in folds])
    oos_returns = np.array([f.oos_return for f in folds])
    return WalkForwardResult(
        folds=folds,
        oos_sharpe_mean=float(oos_sharpes.mean()),
        oos_sharpe_std=float(oos_sharpes.std()),
        oos_sharpe_median=float(np.median(oos_sharpes)),
        oos_return_mean=float(oos_returns.mean()),
        n_folds=len(folds),
        passes=bool(oos_sharpes.mean() > min_oos_sharpe),
    )
