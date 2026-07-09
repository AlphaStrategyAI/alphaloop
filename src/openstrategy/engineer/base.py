"""
Base types for openstrategy.engineer.

Each alpha factor is a pure function from a price series to a series
of weights (0..1) with the same DatetimeIndex. Pure functions are
easy to test, easy to compose, and easy to plug into the M1
walk-forward CV harness.

Conventions:
  - Input: `pd.Series` of close prices with `DatetimeIndex`
  - Output: `pd.Series` of weights, same index, values in [0, 1]
  - Look-ahead bias: zero. A weight at time t may use prices up to
    and including time t, but not beyond. (Most factors shift their
    raw signal by 1 bar to express "act on the close of t+1".)
  - During the warmup period (when the factor cannot yet produce
    a signal), the weight is 0.0. This avoids the silent "always
    invested" default that overstates returns.
"""
from __future__ import annotations

from typing import Callable, Protocol

import pandas as pd


class AlphaFactor(Protocol):
    """Protocol every alpha factor must satisfy.

    A factor takes a close-price series and returns a weight series
    in [0, 1] with the same index. The function MUST be pure
    (no I/O, no RNG state) so that walk-forward CV can replay it
    on each train/test split without side effects.
    """

    def __call__(self, prices: pd.Series, **kwargs) -> pd.Series:  # noqa: D401
        ...


FactorFn = Callable[[pd.Series], pd.Series]


def _empty_weights_like(prices: pd.Series) -> pd.Series:
    """Return a weight series of zeros aligned with the price index."""
    return pd.Series(0.0, index=prices.index, dtype=float)
