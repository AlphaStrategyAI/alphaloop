from __future__ import annotations

_GRIDS: dict[str, tuple[dict[str, object], ...]] = {
    "momentum_12_1": (
        {},
        {"lookback": 126, "skip": 21},
        {"lookback": 189, "skip": 21},
    ),
    "rsi": ({}, {"window": 9}, {"window": 21}),
    "roc": ({}, {"window": 63}, {"window": 126}),
    "macd": (
        {},
        {"fast": 8, "slow": 17, "signal_period": 9},
        {"fast": 12, "slow": 25, "signal_period": 9},
    ),
    "bollinger_zscore": (
        {},
        {"window": 20, "num_std": 2.0},
        {"window": 10, "num_std": 1.5},
    ),
    "ohlr_4_pct": (
        {},
        {"threshold": 80.0},
        {"period": 10, "threshold": 80.0},
    ),
    "pairs_spread": (
        {},
        {"window": 126},
        {"window": 252},
    ),
    "atr_breakout": (
        {},
        {"breakout_window": 20},
        {"breakout_window": 55},
    ),
}


def method_parameter_grid(kind: str) -> tuple[dict[str, object], ...]:
    grid = _GRIDS.get(kind, ({},))
    return tuple(dict(params) for params in grid)
