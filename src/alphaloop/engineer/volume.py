"""
Volume-based alpha factor.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import _empty_weights_like


def obv_slope(
    close: pd.Series,
    volume: pd.Series,
    window: int = 20,
    threshold: float = 0.0,
) -> pd.Series:
    """On-Balance Volume slope: long when OBV is rising.

    OBV accumulates volume on up-closes and subtracts on down-closes.
    A rising OBV suggests accumulation. We use the slope (linear
    regression over `window` bars) of OBV as the signal; long when
    slope > threshold (default 0).
    """
    if close.empty or volume.empty or len(close) < window + 1:
        return _empty_weights_like(close)

    direction = pd.Series(np.sign(close.diff().fillna(0.0).to_numpy()), index=close.index)
    volume_aligned = volume.reindex(close.index).fillna(0.0)
    signed_volume = direction * volume_aligned
    obv = signed_volume.cumsum()

    # Slope via linear regression: cov(x, y) / var(x). With x =
    # arange(window) centered, the slope equals 12 * cov(arange, obv)
    # / (window * (window^2 - 1)). We use a vectorized rolling
    # regression for speed.
    x = np.arange(window, dtype=float)
    x_mean = x.mean()
    x_centered = x - x_mean

    def _slope(s: pd.Series) -> float:
        if s.isna().any() or len(s) < window:
            return np.nan
        y = s.to_numpy() - s.mean()
        return float((x_centered * y).sum() / (x_centered ** 2).sum())

    slopes = obv.rolling(window=window).apply(_slope, raw=False)
    signal = (slopes > threshold).astype(float)
    return signal.shift(1).fillna(0.0)
