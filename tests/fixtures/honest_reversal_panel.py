"""Synthetic cross-sectional reversal panel for offline PIT acceptance.

Test fixture only. It is not shipped in the product and is not a research result.

Process (fixed before looking at verifier output, then checked once):
next-day simple path is built from
``return_t = -0.8 * mean(return_{t-20:t}) + N(0, 0.005)`` with seed 1.
Default mean-reversion settings (lookback 20, entry z 1.0, long only,
drawdown floor -0.25, US 10bp) pass the frozen gates on this panel.
Thresholds are not adjusted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PANEL_SEED = 1
PANEL_REVERSION = 0.8
PANEL_NOISE = 0.005
PANEL_LOOKBACK = 20
PANEL_ASSETS = 8
PANEL_PERIODS = 252 * 6
PANEL_START = "2012-01-03"


def honest_reversal_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    index = pd.bdate_range(PANEL_START, periods=PANEL_PERIODS)
    count = len(index)
    rng = np.random.default_rng(PANEL_SEED)
    columns = [f"S{i}" for i in range(PANEL_ASSETS)]
    returns = np.zeros((count, PANEL_ASSETS))
    for day in range(count):
        if day < PANEL_LOOKBACK:
            returns[day] = rng.normal(0.0, PANEL_NOISE, PANEL_ASSETS)
            continue
        trailing = returns[day - PANEL_LOOKBACK : day].mean(axis=0)
        returns[day] = -PANEL_REVERSION * trailing + rng.normal(0.0, PANEL_NOISE, PANEL_ASSETS)
    prices = pd.DataFrame(
        100.0 * np.exp(np.cumsum(returns, axis=0)),
        index=index,
        columns=columns,
    )
    benchmark = pd.DataFrame(
        {"SPX": 100.0 * np.exp(np.linspace(0.0, 0.02, count))},
        index=index,
    )
    return prices, benchmark
