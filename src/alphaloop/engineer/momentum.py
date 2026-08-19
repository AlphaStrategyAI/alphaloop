"""
Momentum alpha factors.

Long-only "go long if the signal is positive" factors, on a [0, 1]
weight scale. All four use only past data; raw signals are
shifted by one bar to avoid look-ahead bias.

  - rsi(14): Relative Strength Index, overbought/oversold.
  - macd(12, 26, 9): Moving-average convergence divergence.
  - roc(20): Rate of change over 20 bars.
  - momentum_12_1: 12-month minus 1-month momentum (skip the
    short-term reversal month).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import _empty_weights_like


def rsi(prices: pd.Series, window: int = 14, threshold: float = 50.0) -> pd.Series:
    """Long when RSI > threshold (default 50), else flat.

    Wilder's RSI in [0, 100]. The raw RSI is shifted by one bar so
    the weight at bar t uses RSI computed from bars <= t.
    """
    if prices.empty or len(prices) < window + 1:
        return _empty_weights_like(prices)

    delta = prices.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    # Wilder smoothing (EMA with alpha = 1/window)
    avg_gain = gain.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi_raw = 100.0 - (100.0 / (1.0 + rs))
    rsi_val = pd.Series(rsi_raw, index=prices.index).astype(float)
    # When loss == 0 (pure uptrend), RS is inf -> RSI is 100.
    # When gain == 0 (pure downtrend), RS is 0 -> RSI is 0.
    # The 50 fallback only applies during the warmup window.
    warmup = max(window, 14)
    rsi_val = rsi_val.bfill().fillna(50.0)  # warmup neutral
    # For later bars where loss is genuinely 0, force RSI=100
    rsi_val = rsi_val.where(avg_loss > 0, 100.0)
    # For later bars where gain is genuinely 0, force RSI=0
    rsi_val = rsi_val.where(avg_gain > 0, rsi_val)
    signal = (rsi_val > threshold).astype(float)
    return signal.shift(1).fillna(0.0)


def macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> pd.Series:
    """Long when MACD line is above its signal line, else flat."""
    if prices.empty or len(prices) < slow + signal_period:
        return _empty_weights_like(prices)

    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    long_signal = (macd_line > signal_line).astype(float)
    return long_signal.shift(1).fillna(0.0)


def roc(prices: pd.Series, window: int = 20, threshold: float = 0.0) -> pd.Series:
    """Long when n-bar rate of change > threshold (default 0), else flat."""
    if prices.empty or len(prices) < window + 1:
        return _empty_weights_like(prices)

    rate = prices.pct_change(periods=window)
    signal = (rate > threshold).astype(float)
    return signal.shift(1).fillna(0.0)


def momentum_12_1(prices: pd.Series, skip: int = 21, lookback: int = 252) -> pd.Series:
    """12-month-1-month momentum: long when formation-period return is
    positive AND the skipped short-term window was also positive.

    `lookback` is the formation window (default 252 ≈ 12 months).
    `skip` is the most recent bars ignored for short-term reversal
    (default 21 ≈ 1 month), following Jegadeesh and Titman (1993).
    """
    if prices.empty or len(prices) < lookback + skip:
        return _empty_weights_like(prices)

    long_term = prices.pct_change(periods=lookback)
    shifted_long = long_term.shift(skip)
    short_term = prices.pct_change(periods=skip).shift(skip)
    signal = ((shifted_long > 0) & (short_term > 0)).astype(float)
    return signal
