"""Hard deadlines for blocking Yahoo/AkShare market-data IO."""

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import TypeVar

T = TypeVar("T")

# Confirm / gather availability probes must fail fast so the HTTP API stays responsive.
MARKET_DATA_LOAD_TIMEOUT_SEC = float(
    os.environ.get("ALPHALOOP_MARKET_DATA_TIMEOUT_SEC", "25")
)


def cn_market_data_max_workers() -> int:
    raw = os.environ.get("ALPHALOOP_CN_MARKET_MAX_WORKERS", "8")
    return max(1, min(16, int(raw)))


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
