"""Deadlines for blocking Yahoo/AkShare market-data IO."""

from __future__ import annotations

import math
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import TypeVar

T = TypeVar("T")

# Small probes keep this floor. A full v2 pool scales above it.
_BUILTIN_MARKET_DATA_TIMEOUT_SEC = 25.0
MARKET_DATA_LOAD_TIMEOUT_SEC = float(
    os.environ.get("ALPHALOOP_MARKET_DATA_TIMEOUT_SEC", str(_BUILTIN_MARKET_DATA_TIMEOUT_SEC))
)
# Wall-clock budget for one batch. Yahoo runs a batch of 40 two-at-a-time
# (about 20 chart requests back to back, plus 429 backoff). A-share runs one
# wave of the worker pool per batch.
DEFAULT_SEC_PER_BATCH = 60.0
_SEC_PER_BATCH = float(
    os.environ.get("ALPHALOOP_MARKET_DATA_SEC_PER_BATCH", str(DEFAULT_SEC_PER_BATCH))
)
YAHOO_BATCH_SIZE = 40
YAHOO_FETCH_CONCURRENCY = 2


def cn_market_data_max_workers() -> int:
    raw = os.environ.get("ALPHALOOP_CN_MARKET_MAX_WORKERS", "8")
    return max(1, min(16, int(raw)))


def load_deadline_seconds(symbol_count: int, *, batch_size: int) -> float:
    """Overall deadline for one ``load_daily``.

    An explicit ``ALPHALOOP_MARKET_DATA_TIMEOUT_SEC`` (or a test that replaces
    ``MARKET_DATA_LOAD_TIMEOUT_SEC``) is honored as a hard cap. The built-in
    25s floor is too small for a few hundred names, so that case scales with
    the number of batches.
    """
    configured = MARKET_DATA_LOAD_TIMEOUT_SEC
    if configured != _BUILTIN_MARKET_DATA_TIMEOUT_SEC:
        return configured
    batches = math.ceil(max(symbol_count, 1) / max(batch_size, 1))
    return max(configured, batches * _SEC_PER_BATCH)


def run_with_deadline(seconds: float, fn: Callable[[], T]) -> T:
    """Run blocking provider IO on a worker thread with an overall deadline."""
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="market-io")
    future = pool.submit(fn)
    try:
        return future.result(timeout=seconds)
    except FuturesTimeoutError:
        raise TimeoutError(f"market data call exceeded {seconds:.0f}s deadline") from None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
