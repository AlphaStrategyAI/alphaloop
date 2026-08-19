from __future__ import annotations

import pandas as pd


def compute_strategy_returns(prices: pd.Series, weights: pd.Series) -> pd.Series:
    asset_ret = prices.pct_change().fillna(0.0)
    lagged = weights.reindex(prices.index).shift(1).fillna(0.0)
    return lagged * asset_ret
