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


def data_source_id_for_market(market: object) -> str:
    from engine.research.models import Market

    if market is Market.CN:
        return AKSHARE_SINA_DATA_SOURCE_ID
    return DEFAULT_DATA_SOURCE_ID
