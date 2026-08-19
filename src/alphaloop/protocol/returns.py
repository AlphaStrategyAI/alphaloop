from __future__ import annotations

import pandas as pd


def compute_strategy_returns(
    prices: pd.Series,
    weights: pd.Series,
    *,
    cost_bps: float = 0.0,
) -> pd.Series:
    asset_ret = prices.pct_change().fillna(0.0)
    position = weights.reindex(prices.index).shift(1).fillna(0.0)
    gross = position * asset_ret
    turnover = position.diff().abs().fillna(0.0)
    cost = turnover * (float(cost_bps) / 10_000.0)
    return gross - cost
