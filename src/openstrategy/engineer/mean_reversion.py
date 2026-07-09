"""
Mean-reversion alpha factors.

Long when a price has fallen "too far" relative to its recent
distribution. Symmetric short versions are not implemented; v1.0
is long-only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import _empty_weights_like


def bollinger_zscore(
    prices: pd.Series,
    window: int = 20,
    num_std: float = 1.5,
    invert: bool = True,
) -> pd.Series:
    """Long when price is below `moving_avg - num_std * std`.

    With `invert=True` (the default), this is a long-only mean
    reversion: buy when the price is depressed. With `invert=False`,
    this becomes a momentum (long when price is above upper band).
    """
    if prices.empty or len(prices) < window:
        return _empty_weights_like(prices)

    ma = prices.rolling(window=window).mean()
    sd = prices.rolling(window=window).std()
    zscore = (prices - ma) / sd.replace(0.0, np.nan)
    if invert:
        signal = (zscore < -num_std).astype(float)
    else:
        signal = (zscore > num_std).astype(float)
    return signal.shift(1).fillna(0.0)


def ohlr_4_pct(
    ohlc: pd.DataFrame,
    threshold: float = 0.0,
) -> pd.Series:
    """Larry Williams' %R (Williams Percent Range).

    Inputs: a DataFrame with columns `high`, `low`, `close` (DatetimeIndex).
    Long when %R < -threshold (default 0 means %R < 0, i.e. close is
    below the recent high, a "near-bottom" mean reversion setup).
    """
    if ohlc.empty or len(ohlc) < 14:
        return pd.Series(0.0, index=ohlc.index, dtype=float)
    high = ohlc["high"]
    low = ohlc["low"]
    close = ohlc["close"]
    period = 14
    hh = high.rolling(period).max()
    ll = low.rolling(period).min()
    denom = (hh - ll).replace(0.0, np.nan)
    pct_r = -100.0 * (hh - close) / denom
    # Standard %R range: -100 (bottom) to 0 (top).
    # Mean-reversion: long when %R < threshold (i.e. very low).
    pct_r = pd.Series(pct_r, index=ohlc.index).astype(float)
    pct_r = pct_r.bfill().fillna(-50.0)
    signal = (pct_r < -threshold).astype(float) if threshold > 0 else (pct_r < 0).astype(float)
    return signal.shift(1).fillna(0.0)


def pairs_spread(
    prices_a: pd.Series,
    prices_b: pd.Series,
    window: int = 60,
    num_std: float = 1.5,
) -> pd.Series:
    """Long A / short B when the spread (log-px) is below its MA by
    `num_std` standard deviations.

    This is a classic pairs-trading mean-reversion factor on a single
    pair. Output is the weight for the LONG leg (A). The short leg
    weight is `-1 * output`; v1.0 is long-only, so we only emit the
    long weight. The hedge ratio is implicitly 1.0 (you can scale the
    short leg by the OLS beta in production).
    """
    if prices_a.empty or prices_b.empty:
        return _empty_weights_like(prices_a)

    # Align on inner join
    joined = pd.concat([prices_a.rename("a"), prices_b.rename("b")], axis=1, join="inner").dropna()
    if joined.empty or len(joined) < window:
        out = pd.Series(0.0, index=prices_a.index)
        return out.reindex(prices_a.index).fillna(0.0)

    log_a = pd.Series(np.log(joined["a"].to_numpy()), index=joined.index)
    log_b = pd.Series(np.log(joined["b"].to_numpy()), index=joined.index)
    spread = log_a - log_b
    ma = spread.rolling(window=window).mean()
    sd = spread.rolling(window=window).std()
    zscore = (spread - ma) / sd.replace(0.0, np.nan)
    long_a = (zscore < -num_std).astype(float)  # spread depressed -> A cheap
    # Reindex back to prices_a's index (preserving original NaNs)
    out = long_a.reindex(prices_a.index).fillna(0.0)
    return out.shift(1).fillna(0.0)
