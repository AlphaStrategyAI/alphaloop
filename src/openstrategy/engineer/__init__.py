"""
openstrategy.engineer - Alpha factor library.

Ten canonical factors across four families:

  Momentum (4):
    - rsi
    - macd
    - roc
    - momentum_12_1

  Mean Reversion (3):
    - bollinger_zscore
    - ohlr_4_pct (Williams %R)
    - pairs_spread

  Volatility (2):
    - atr_breakout
    - parkinson_hist_vol

  Volume (1):
    - obv_slope

All factors are pure functions: input a price series (and optionally
OHLCV columns), output a weight series in [0, 1] with the same
DatetimeIndex. No state, no I/O, no RNG. This makes them trivial
to compose, test, and plug into walk-forward CV.
"""
from .momentum import macd, momentum_12_1, roc, rsi
from .mean_reversion import bollinger_zscore, ohlr_4_pct, pairs_spread
from .volatility import atr_breakout, parkinson_hist_vol
from .volume import obv_slope

__all__ = [
    # Momentum
    "rsi",
    "macd",
    "roc",
    "momentum_12_1",
    # Mean Reversion
    "bollinger_zscore",
    "ohlr_4_pct",
    "pairs_spread",
    # Volatility
    "atr_breakout",
    "parkinson_hist_vol",
    # Volume
    "obv_slope",
]
