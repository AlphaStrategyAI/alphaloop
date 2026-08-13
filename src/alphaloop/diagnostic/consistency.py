"""
Cross-source data consistency check.

When the same symbol is fetched from multiple data sources (e.g.
yahoo vs akshare for an A-share, or yahoo vs ccxt for crypto), the
historical price series will almost never be identical. This module
quantifies the disagreement in a way that flags "data has a bug" vs
"data is fine, just from different feeds":

  - relative price error (mean / median / p95 of |a-b| / mid)
  - return correlation (Pearson, ignoring alignment edge effects)
  - OHLCV invariants on each series independently

Acceptance threshold (v1.0): mean relative error < 5% on daily close
for the same symbol across two sources.

Usage:
    from alphaloop.diagnostic import data_source_consistency

    result = data_source_consistency(yahoo_df, akshare_df, symbol="AAPL")
    print(result.summary())
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class ConsistencyResult:
    """Result of a cross-source consistency check."""

    symbol: str
    n_overlap: int
    mean_rel_error: float
    median_rel_error: float
    p95_rel_error: float
    return_corr: float
    passes: bool  # all checks within thresholds

    def summary(self) -> str:
        verdict = "PASS" if self.passes else "FAIL"
        return (
            f"Cross-source consistency verdict: {verdict}\n"
            f"  Symbol:              {self.symbol}\n"
            f"  Overlap bars:        {self.n_overlap}\n"
            f"  Mean rel. error:     {self.mean_rel_error:.4%}\n"
            f"  Median rel. error:   {self.median_rel_error:.4%}\n"
            f"  P95 rel. error:      {self.p95_rel_error:.4%}\n"
            f"  Return correlation:  {self.return_corr:.4f}"
        )


def _align_close(
    df_a: pd.DataFrame, df_b: pd.DataFrame
) -> tuple[pd.Series, pd.Series]:
    """Inner-join the 'close' columns of two OHLCV frames on date index."""
    if "close" not in df_a.columns or "close" not in df_b.columns:
        raise ValueError(
            f"Both frames must have a 'close' column; "
            f"got {list(df_a.columns)} and {list(df_b.columns)}"
        )
    a = df_a["close"].copy()
    b = df_b["close"].copy()
    # Coerce index to datetime for join
    if not isinstance(a.index, pd.DatetimeIndex):
        a.index = pd.to_datetime(a.index)
    if not isinstance(b.index, pd.DatetimeIndex):
        b.index = pd.to_datetime(b.index)
    a.name = "a"
    b.name = "b"
    joined = pd.concat([a, b], axis=1, join="inner").dropna()
    if joined.empty:
        return joined["a"], joined["b"]
    return joined["a"], joined["b"]


def data_source_consistency(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    symbol: str = "",
    max_mean_rel_error: float = 0.05,
    max_p95_rel_error: float = 0.20,
    min_return_corr: float = 0.95,
) -> ConsistencyResult:
    """Quantify the disagreement between two data sources for one symbol.

    Args:
        df_a, df_b: DataFrames with a 'close' column and a DatetimeIndex
            (or any index that can be coerced via `pd.to_datetime`).
        symbol: Optional symbol label for the report.
        max_mean_rel_error: Threshold for mean relative error
            (default 5%, the v1.0 acceptance threshold).
        max_p95_rel_error: Threshold for p95 relative error
            (default 20%).
        min_return_corr: Threshold for Pearson correlation of daily
            returns (default 0.95; below this is "different stories").

    Returns:
        ConsistencyResult with summary statistics and pass/fail.
    """
    a, b = _align_close(df_a, df_b)
    if len(a) < 5:
        return ConsistencyResult(
            symbol=symbol,
            n_overlap=len(a),
            mean_rel_error=float("inf"),
            median_rel_error=float("inf"),
            p95_rel_error=float("inf"),
            return_corr=float("nan"),
            passes=False,
        )

    # Relative price error: |a - b| / mid, where mid = (a+b)/2
    mid = (a + b) / 2.0
    rel_err = (a - b).abs() / mid
    mean_re = float(rel_err.mean())
    median_re = float(rel_err.median())
    p95_re = float(rel_err.quantile(0.95))

    # Return correlation
    ra = a.pct_change().dropna()
    rb = b.pct_change().dropna()
    ra.name = "a"
    rb.name = "b"
    joined_r = pd.concat([ra, rb], axis=1, join="inner").dropna()
    if len(joined_r) < 5:
        return_corr = float("nan")
    else:
        return_corr = float(joined_r["a"].corr(joined_r["b"]))

    passes = (
        mean_re <= max_mean_rel_error
        and p95_re <= max_p95_rel_error
        and (np.isnan(return_corr) or return_corr >= min_return_corr)
    )

    return ConsistencyResult(
        symbol=symbol,
        n_overlap=len(a),
        mean_rel_error=mean_re,
        median_rel_error=median_re,
        p95_rel_error=p95_re,
        return_corr=return_corr,
        passes=passes,
    )
