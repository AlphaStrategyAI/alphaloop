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
# Enough waves for a 300-name A-share pool (8 at a time) and a 503-name
# Yahoo pool (40 at a time). The desktop command timeout stays one margin
# above this budget so the shell does not disconnect first.
SHELL_TIMEOUT_BATCHES = 40
SHELL_TIMEOUT_MARGIN_SEC = 120.0
CN_HTTP_TIMEOUT_SEC = 20.0


def cn_market_data_max_workers() -> int:
    raw = os.environ.get("ALPHALOOP_CN_MARKET_MAX_WORKERS", "8")
    return max(1, min(16, int(raw)))


def shell_command_timeout_seconds(
    *,
    explicit: float | None,
    sec_per_batch: float,
) -> float:
    """How long the desktop may wait on one engine command.

    An explicit ``ALPHALOOP_MARKET_DATA_TIMEOUT_SEC`` is the engine cap, so
    the shell waits that long plus a margin. Otherwise the shell waits for
    the largest v2 pool budget plus the same margin.
    """
    if explicit is not None:
        return explicit + SHELL_TIMEOUT_MARGIN_SEC
    return sec_per_batch * SHELL_TIMEOUT_BATCHES + SHELL_TIMEOUT_MARGIN_SEC


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
    """Run blocking provider IO on a worker thread with an overall deadline.

    On timeout the generation is cancelled, so queued symbol fetches do not
    open another connection. The in-flight HTTP session is closed.
    """
    from engine.research.market_data_cancel import (
        begin_market_data_generation,
        bind_market_data_generation,
        cancel_market_data,
        end_market_data_generation,
    )

    generation, token = begin_market_data_generation()

    def _run() -> T:
        worker_token = bind_market_data_generation(generation)
        try:
            return fn()
        finally:
            end_market_data_generation(worker_token)

    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="market-io")
    future = pool.submit(_run)
    try:
        return future.result(timeout=seconds)
    except FuturesTimeoutError:
        cancel_market_data()
        raise TimeoutError(f"market data call exceeded {seconds:.0f}s deadline") from None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        end_market_data_generation(token)
