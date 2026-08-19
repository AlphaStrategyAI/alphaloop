from __future__ import annotations

import pandas as pd

from alphaloop.protocol.returns import compute_strategy_returns


def test_lagged_weights_times_asset_returns():
    prices = pd.Series([100.0, 110.0, 121.0], index=pd.RangeIndex(3))
    weights = pd.Series([0.0, 1.0, 1.0], index=prices.index)
    out = compute_strategy_returns(prices, weights)
    assert list(out.index) == list(prices.index)
    assert out.iloc[0] == 0.0
    assert out.iloc[1] == 0.0
    assert abs(float(out.iloc[2]) - 0.1) < 1e-12


def test_all_ones_is_not_raw_pct_change_on_first_bar():
    prices = pd.Series([100.0, 110.0, 121.0], index=pd.RangeIndex(3))
    weights = pd.Series([1.0, 1.0, 1.0], index=prices.index)
    out = compute_strategy_returns(prices, weights)
    raw = prices.pct_change()
    assert out.iloc[0] == 0.0
    assert abs(float(out.iloc[1]) - float(raw.iloc[1])) < 1e-12
    assert not out.equals(raw)
