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

from alphaloop.protocol.returns import compute_strategy_returns


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
    passes: bool  # mean OOS Sharpe > 0, halves stable when evaluable, median > 0 if n_folds >= 3
    oos_returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    first_half_sharpe: float = 0.0
    second_half_sharpe: float = 0.0
    regime_stable: bool = True

    def summary(self) -> str:
        verdict = "PASS" if self.passes else "FAIL"
        return (
            f"Walk-Forward CV verdict: {verdict}\n"
            f"  N folds:           {self.n_folds}\n"
            f"  OOS Sharpe mean:   {self.oos_sharpe_mean:.3f}\n"
            f"  OOS Sharpe std:    {self.oos_sharpe_std:.3f}\n"
            f"  OOS Sharpe median: {self.oos_sharpe_median:.3f}\n"
            f"  OOS return mean:   {self.oos_return_mean:.3%}\n"
            f"  Regime stable:     {self.regime_stable}\n"
            f"  First-half SR:     {self.first_half_sharpe:.3f}\n"
            f"  Second-half SR:    {self.second_half_sharpe:.3f}"
        )


def _annualized_sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    """Annualized Sharpe ratio (no risk-free rate)."""
    if returns.empty or returns.std() == 0:
        return 0.0
    return float(returns.mean() / returns.std() * np.sqrt(periods_per_year))


MIN_REGIME_OBSERVATIONS = 30


def chronological_half_sharpes(
    returns: pd.Series,
    periods_per_year: int = 252,
) -> tuple[float, float, bool]:
    """Split *returns* at the midpoint and Sharpe each half.

    Returns ``(first_half_sharpe, second_half_sharpe, evaluated)``.
    ``evaluated`` is False when ``len(returns) < MIN_REGIME_OBSERVATIONS``.
    """
    if returns is None or len(returns) < MIN_REGIME_OBSERVATIONS:
        return 0.0, 0.0, False
    mid = len(returns) // 2
    first = _annualized_sharpe(returns.iloc[:mid], periods_per_year)
    second = _annualized_sharpe(returns.iloc[mid:], periods_per_year)
    return first, second, True


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
    embargo_size: int = 0,
    cost_bps: float = 0.0,
) -> WalkForwardResult:
    """Walk-forward cross-validation with optional embargo and costs.

    Args:
        prices: Price series with a DatetimeIndex.
        strategy_fn: Function that takes a price series and returns
            a series of position weights or signals (same length).
        train_size: Number of bars in the training window.
        test_size: Number of bars in the test (out-of-sample) window.
        step_size: How many bars to roll forward each fold. Defaults
            to `test_size` (non-overlapping test windows).
        periods_per_year: For annualizing Sharpe. Default 252 (daily).
            min_oos_sharpe: Threshold for `result.passes` (default 0.0,
            i.e. mean OOS Sharpe must be positive). When concatenated
            OOS length is at least 30, both chronological halves must
            also have positive Sharpe. When there are at least three
            folds, the median fold OOS Sharpe must also exceed this
            threshold.
        embargo_size: Bars skipped between the last train bar and the
            first test bar (López de Prado Ch. 7 embargo). Default 0
            preserves historical fold geometry.
        cost_bps: One-way transaction cost in basis points applied via
            `compute_strategy_returns`.

    Returns:
        WalkForwardResult with per-fold details and aggregate stats.
    """
    if embargo_size < 0:
        raise ValueError(f"embargo_size must be >= 0, got {embargo_size}")
    if step_size is None:
        step_size = test_size
    if not isinstance(prices, pd.Series):
        raise TypeError(f"prices must be a pandas Series, got {type(prices)}")
    required = train_size + embargo_size + test_size
    if len(prices) < required:
        raise ValueError(
            f"Need at least train_size+embargo_size+test_size = {required} bars, "
            f"got {len(prices)}"
        )

    folds: List[WalkForwardFold] = []
    oos_parts: list[pd.Series] = []
    fold_id = 0
    i = 0
    idx = prices.index
    while i + train_size + embargo_size + test_size <= len(prices):
        test_start_i = i + train_size + embargo_size
        test_end_i = test_start_i + test_size
        history = prices.iloc[:test_end_i]
        all_weights = strategy_fn(history)
        net = compute_strategy_returns(history, all_weights, cost_bps=cost_bps)
        train_returns = net.iloc[i : i + train_size]
        test_returns = net.iloc[test_start_i:test_end_i]
        oos_parts.append(test_returns)

        train_start = pd.Timestamp(idx[i])
        train_end = pd.Timestamp(idx[i + train_size - 1])
        test_start = pd.Timestamp(idx[test_start_i])
        test_end = pd.Timestamp(idx[test_end_i - 1])

        folds.append(
            WalkForwardFold(
                fold_id=fold_id,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_sharpe=_annualized_sharpe(train_returns, periods_per_year),
                oos_sharpe=_annualized_sharpe(test_returns, periods_per_year),
                oos_return=float((1.0 + test_returns).prod() - 1.0),
                oos_max_drawdown=_max_drawdown(test_returns),
            )
        )

        fold_id += 1
        i += step_size

    concat = pd.concat(oos_parts) if oos_parts else pd.Series(dtype=float)
    if not concat.empty:
        concat = concat[~concat.index.duplicated(keep="first")]
    first, second, evaluated = chronological_half_sharpes(concat, periods_per_year)
    regime_stable = (first > 0.0 and second > 0.0) if evaluated else True

    if not folds:
        return WalkForwardResult(
            folds=[],
            oos_sharpe_mean=0.0,
            oos_sharpe_std=0.0,
            oos_sharpe_median=0.0,
            oos_return_mean=0.0,
            n_folds=0,
            passes=False,
            oos_returns=concat,
            first_half_sharpe=first,
            second_half_sharpe=second,
            regime_stable=regime_stable,
        )

    oos_sharpes = np.array([f.oos_sharpe for f in folds])
    oos_returns = np.array([f.oos_return for f in folds])
    median = float(np.median(oos_sharpes))
    median_ok = True if len(folds) < 3 else bool(median > min_oos_sharpe)
    return WalkForwardResult(
        folds=folds,
        oos_sharpe_mean=float(oos_sharpes.mean()),
        oos_sharpe_std=float(oos_sharpes.std()),
        oos_sharpe_median=median,
        oos_return_mean=float(oos_returns.mean()),
        n_folds=len(folds),
        passes=bool(oos_sharpes.mean() > min_oos_sharpe) and regime_stable and median_ok,
        oos_returns=concat,
        first_half_sharpe=first,
        second_half_sharpe=second,
        regime_stable=regime_stable,
    )
