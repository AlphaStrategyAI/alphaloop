"""Simulation calendar window used at confirm time (matches DefaultRoundBuilder)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta


def planned_data_window(
    now: datetime | None = None,
    *,
    years_back: int = 12,
) -> tuple[date, date]:
    today = (now or datetime.now(UTC)).date()
    start = today - timedelta(days=365 * years_back)
    return start, today


DEFAULT_DATA_SOURCE_ID = "yahoo_daily"
AKSHARE_SINA_DATA_SOURCE_ID = "akshare_sina_daily"
_CN_LISTING_SUFFIXES = (".SH", ".SZ", ".BJ")


def is_cn_listed_symbol(symbol: str) -> bool:
    """True for instruments the AkShare adapter loads, including A-share listings."""
    return (
        symbol.endswith(_CN_LISTING_SUFFIXES)
        or symbol == "CBA00101.CS"
        or symbol.startswith(("CN_BOND:", "CN_FUND:"))
    )


def data_source_id_for_market(market: object) -> str:
    from engine.research.models import Market

    if market is Market.CN:
        return AKSHARE_SINA_DATA_SOURCE_ID
    return DEFAULT_DATA_SOURCE_ID


def data_source_id_for_symbol(symbol: str, market: object | None = None) -> str:
    """A-share listings use AkShare. Every other symbol keeps the market rule."""
    if is_cn_listed_symbol(symbol):
        return AKSHARE_SINA_DATA_SOURCE_ID
    if market is None:
        return DEFAULT_DATA_SOURCE_ID
    return data_source_id_for_market(market)


def data_source_ids_for_symbols(
    symbols: tuple[str, ...],
    market: object | None = None,
) -> tuple[str, ...]:
    """Distinct source ids for a pool, Yahoo before AkShare when both apply."""
    if not symbols:
        if market is None:
            return (DEFAULT_DATA_SOURCE_ID,)
        return (data_source_id_for_market(market),)
    present = {data_source_id_for_symbol(symbol, market) for symbol in symbols}
    ordered = [
        source_id
        for source_id in (DEFAULT_DATA_SOURCE_ID, AKSHARE_SINA_DATA_SOURCE_ID)
        if source_id in present
    ]
    extras = sorted(present.difference(ordered))
    return tuple(ordered + extras)


def data_source_id_for_symbols(
    symbols: tuple[str, ...],
    market: object | None = None,
) -> str:
    """Single id stored at confirm. AkShare only when every symbol is CN-listed.

    A mixed pool keeps ``data_source_id_for_market`` so the window key stays the
    historical single id. The loader uses the same all-CN test.
    """
    if symbols and all(is_cn_listed_symbol(symbol) for symbol in symbols):
        return AKSHARE_SINA_DATA_SOURCE_ID
    if market is None:
        return DEFAULT_DATA_SOURCE_ID
    return data_source_id_for_market(market)
