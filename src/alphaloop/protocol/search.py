from __future__ import annotations

_GRIDS: dict[str, tuple[dict[str, object], ...]] = {
    "momentum_12_1": (
        {},
        {"lookback": 126, "skip": 21},
        {"lookback": 189, "skip": 21},
    ),
    "rsi": ({}, {"window": 9}, {"window": 21}),
    "roc": ({}, {"window": 63}, {"window": 126}),
}


def method_parameter_grid(kind: str) -> tuple[dict[str, object], ...]:
    grid = _GRIDS.get(kind, ({},))
    return tuple(dict(params) for params in grid)
