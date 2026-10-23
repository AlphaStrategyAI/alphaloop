"""Synthetic daily bars for tests. Off unless ALPHALOOP_OFFLINE_MARKET_DATA=1."""

from __future__ import annotations

import os
import zlib
from datetime import date

import numpy as np
import pandas as pd

OFFLINE_MARKET_DATA_ENV = "ALPHALOOP_OFFLINE_MARKET_DATA"


def offline_market_data_enabled() -> bool:
    """True only for the explicit test flag. Unset, empty, and ``0`` stay on the live adapters."""
    return os.environ.get(OFFLINE_MARKET_DATA_ENV, "").strip() == "1"


class OfflineMarketDataAdapter:
    """Deterministic business-day closes. No Yahoo and no Sina."""

    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        if not symbols or end < start:
            return pd.DataFrame()
        index = pd.bdate_range(start, end)
        if len(index) == 0:
            return pd.DataFrame()
        columns = {symbol: _closes(symbol, index) for symbol in symbols}
        return pd.DataFrame(columns, index=index)


def _closes(symbol: str, index: pd.DatetimeIndex) -> pd.Series:
    seed = zlib.crc32(symbol.encode("utf-8")) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)
    shocks = rng.normal(0.0003, 0.012, size=len(index))
    levels = 100.0 * np.exp(np.cumsum(shocks))
    return pd.Series(levels, index=index, name=symbol)
