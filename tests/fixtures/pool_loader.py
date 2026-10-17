from __future__ import annotations

from datetime import date

import pandas as pd


class AllSymbolsAvailableLoader:
    """Offline stub: every requested symbol has at least one daily bar."""

    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        index = pd.to_datetime([start, end])
        return pd.DataFrame(
            {symbol: pd.Series([100.0, 101.0], index=index, name=symbol) for symbol in symbols}
        )
