"""
Volatility-based alpha factors.

Both factors work on raw OHLCV data (or close-only for ATR).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import _empty_weights_like


def atr_breakout(
    ohlc: pd.DataFrame,
    atr_window: int = 14,
    breakout_window: int = 50,
    atr_multiplier: float = 1.5,
) -> pd.Series:
    """Long when price breaks out above (rolling_max + atr * k).

    Inputs: a DataFrame with `high`, `low`, `close` columns.
    Uses Average True Range (ATR) over `atr_window` and a rolling
    high over `breakout_window`.
    """
    if ohlc.empty or len(ohlc) < max(atr_window, breakout_window) + 1:
        return _empty_weights_like(ohlc["close"])

    high = ohlc["high"]
    low = ohlc["low"]
    close = ohlc["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = tr.ewm(alpha=1.0 / atr_window, adjust=False, min_periods=atr_window).mean()
    # Breakout: close[t] exceeds the highest close over the previous
    # `breakout_window` bars (excluding t itself) plus an ATR buffer.
    # We shift(1) so the rolling window is strictly past.
    rolling_close_high = close.rolling(window=breakout_window).max().shift(1)
    threshold = rolling_close_high + atr_multiplier * atr
    breakout = (close > threshold).astype(float)
    return breakout.shift(1).fillna(0.0)


def parkinson_hist_vol(prices: pd.Series, window: int = 30) -> pd.Series:
    """Parkinson historical volatility (annualized).

    IMPORTANT: this is a *feature*, not a long-only signal. Parkinson
    volatility in itself does not predict returns; it is useful as
    input to other factors (e.g. vol-targeted position sizing) or as
    a sanity-check feature for ML models. We expose it via the same
    `factor_fn(prices) -> weights` signature so it can flow through
    the same harness, but downstream code should NOT use its sign as
    a direction signal.

    Inputs: a single close-price series.
    Returns: a series of annualized Parkinson vol estimates (>=0).
    """
    if prices.empty or len(prices) < window + 1:
        return _empty_weights_like(prices)

    # Parkinson (1980): sigma^2 = (1 / 4 ln 2) * mean((ln(H/L))^2)
    # We approximate H_t and L_t from high-frequency close using
    # rolling max / min, which is a simplification but preserves the
    # variance-scaling properties.
    rolling_high = prices.rolling(window=window).max()
    rolling_low = prices.rolling(window=window).min()
    log_hl = np.log((rolling_high / rolling_low).replace(0.0, np.nan))
    parkinson_var = (log_hl ** 2) / (4.0 * np.log(2.0))
    # Annualize: scale by trading days per year / window
    annualized = pd.Series(
        np.sqrt(parkinson_var * (252.0 / window)),
        index=prices.index,
    )
    return annualized.bfill().fillna(0.0)
