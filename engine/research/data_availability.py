"""Distinguish transient market-data outages from per-symbol missing bars."""

from __future__ import annotations

from typing import Any

import httpx
import pandas as pd

from engine.research.data_errors import DataPipelineError
from engine.research.user_errors import UserFacingError

TRANSIENT_DATA_MESSAGE = "行情数据源暂时不可用，请稍后重试"
TRANSIENT_DATA_CODE = "DATA_SOURCE_UNAVAILABLE"


def transient_data_error() -> UserFacingError:
    return UserFacingError(TRANSIENT_DATA_CODE, TRANSIENT_DATA_MESSAGE)


def classify_load_failure(error: BaseException) -> UserFacingError | None:
    if isinstance(error, DataPipelineError):
        if error.code == TRANSIENT_DATA_CODE:
            return transient_data_error()
        return UserFacingError(error.code, error.message)
    if isinstance(error, UserFacingError):
        return error
    if isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code in {403, 429, 500, 502, 503, 504}:
            return transient_data_error()
    if isinstance(error, (httpx.TimeoutException, httpx.ConnectError, TimeoutError, OSError)):
        return transient_data_error()
    text = str(error).lower()
    if any(
        token in text
        for token in (
            "too many requests",
            "rate limit",
            "429",
            "403 forbidden",
            "timed out",
            "timeout",
            "connection reset",
            "connection refused",
            "temporarily unavailable",
        )
    ):
        return transient_data_error()
    return None


def symbols_with_any_bars(frame: pd.DataFrame, symbols: tuple[str, ...]) -> tuple[str, ...]:
    available: list[str] = []
    for symbol in symbols:
        if symbol not in frame.columns:
            continue
        series = frame[symbol]
        if series.notna().sum() > 0:
            available.append(symbol)
    return tuple(available)


def raise_if_total_source_outage(symbols: tuple[str, ...], frame: pd.DataFrame) -> None:
    """All symbols missing bars usually means the provider failed, not bad tickers."""
    if not symbols:
        return
    if frame is None or frame.empty:
        raise transient_data_error()
    if not symbols_with_any_bars(frame, symbols):
        raise transient_data_error()
