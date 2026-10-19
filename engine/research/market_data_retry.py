"""Retry provider calls that come back HTTP 429, honoring Retry-After."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from engine.research.data_availability import market_data_rate_limited

T = TypeVar("T")

MAX_RATE_LIMIT_ATTEMPTS = 4


def is_rate_limited(error: BaseException) -> bool:
    status = getattr(getattr(error, "response", None), "status_code", None)
    if status == 429:
        return True
    if type(error).__name__ == "YFRateLimitError":
        return True
    text = str(error).lower()
    return "429" in text or "too many requests" in text or "rate limit" in text


def retry_after_seconds(error: BaseException, attempt: int) -> float:
    """Prefer a numeric Retry-After header; otherwise exponential backoff, capped at 60s."""
    headers = getattr(getattr(error, "response", None), "headers", None)
    raw = headers.get("Retry-After") if headers is not None and hasattr(headers, "get") else None
    if raw is not None:
        try:
            return max(0.0, float(str(raw).strip()))
        except ValueError:
            pass
    return min(60.0, float(2**attempt))


def call_with_rate_limit_retry(
    fn: Callable[[], T],
    *,
    attempts: int = MAX_RATE_LIMIT_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    last: BaseException | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as error:
            if not is_rate_limited(error):
                raise
            last = error
            if attempt + 1 >= attempts:
                break
            sleep(retry_after_seconds(error, attempt))
    raise market_data_rate_limited() from last
