"""In-process progress for a market-data load. Safe to read from another request."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MarketDataProgress:
    done: int
    total: int
    source: str


_lock = threading.Lock()
_current: MarketDataProgress | None = None


def set_market_data_progress(done: int, total: int, source: str) -> None:
    global _current
    with _lock:
        _current = MarketDataProgress(done, total, source)


def clear_market_data_progress() -> None:
    global _current
    with _lock:
        _current = None


def market_data_progress() -> MarketDataProgress | None:
    with _lock:
        return _current


def market_data_progress_payload() -> dict[str, int | str] | None:
    progress = market_data_progress()
    if progress is None:
        return None
    return {"done": progress.done, "total": progress.total, "source": progress.source}
