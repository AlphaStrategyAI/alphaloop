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
