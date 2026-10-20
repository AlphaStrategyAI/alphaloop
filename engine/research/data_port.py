"""Build a research's market-data port from that research's own source id."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from engine.research.a1_copy import DATA_SOURCE_UNBOUND
from engine.research.data_availability import market_data_timeout
from engine.research.market_data_timeouts import (
    YAHOO_BATCH_SIZE,
    cn_market_data_max_workers,
    load_deadline_seconds,
    run_with_deadline,
)
from engine.research.planned_data_window import (
    AKSHARE_SINA_DATA_SOURCE_ID,
    DEFAULT_DATA_SOURCE_ID,
    is_cn_listed_symbol,
)
from engine.research.user_errors import UserFacingError

LEGACY_SOURCE_IDS = frozenset({DEFAULT_DATA_SOURCE_ID, AKSHARE_SINA_DATA_SOURCE_ID})


@dataclass(frozen=True, slots=True)
class BoundDataPort:
    """One adapter chosen for this load, with the same empty-symbol and deadline guard."""

    inner: object

    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        from engine.research.data_errors import EmptySymbolsError

        if not symbols:
            raise EmptySymbolsError()

        def _load() -> pd.DataFrame:
            return self.inner.load_daily(symbols, start, end)  # type: ignore[attr-defined, no-any-return]

        batch = (
            cn_market_data_max_workers()
            if symbols and all(is_cn_listed_symbol(symbol) for symbol in symbols)
            else YAHOO_BATCH_SIZE
        )
        try:
            return run_with_deadline(
                load_deadline_seconds(len(symbols), batch_size=batch),
                _load,
            )
        except TimeoutError:
            raise market_data_timeout(len(symbols)) from None


def data_port_for_symbols(symbols: tuple[str, ...]) -> BoundDataPort:
    """Legacy symbol rule: an all-CN pool uses AkShare; anything else uses Yahoo.

    This is the historical fetch split, not a new default selection. Callers that
    do not yet have a research source id (pool shrink before confirm) use it.
    """
    from engine.research.gather import AkShareDataAdapter, YahooDataAdapter
    from engine.research.planned_data_window import is_cn_listed_symbol

    if symbols and all(is_cn_listed_symbol(symbol) for symbol in symbols):
        return BoundDataPort(AkShareDataAdapter())
    return BoundDataPort(YahooDataAdapter())


def data_port_for_research(research: object) -> BoundDataPort:
    """Port for a research. Unknown source ids are not silently sent to Yahoo."""
    source_id = getattr(research, "data_source_id", "")
    if source_id not in LEGACY_SOURCE_IDS:
        raise UserFacingError("DATA_SOURCE_UNBOUND", DATA_SOURCE_UNBOUND)
    universe = research.brief.universe.value  # type: ignore[attr-defined]
    symbols = universe.symbols if universe is not None else ()
    return data_port_for_symbols(symbols)
