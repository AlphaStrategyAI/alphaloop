"""Distinguish transient market-data outages from per-symbol missing bars."""

from __future__ import annotations

from typing import Any

import httpx
import pandas as pd

from engine.research.data_errors import DataPipelineError
from engine.research.user_errors import UserFacingError

TRANSIENT_DATA_MESSAGE = "行情数据源暂时不可用，请稍后重试"
TRANSIENT_DATA_CODE = "DATA_SOURCE_UNAVAILABLE"
MARKET_DATA_FAILURE_CODES = frozenset(
    {
        TRANSIENT_DATA_CODE,
        "MARKET_DATA_TIMEOUT",
        "MARKET_DATA_RATE_LIMITED",
        "MARKET_DATA_FETCH_FAILED",
    }
)
_EMPTY_FRAME_DETAIL = "provider returned an empty price frame"


def _technical(error: BaseException) -> str:
    text = str(error).strip()
    name = type(error).__name__
    if not text or text == TRANSIENT_DATA_MESSAGE or text == name:
        return name
    return f"{name}: {text}"


def transient_data_error(
    detail: str | None = None,
    *,
    params: dict[str, Any] | None = None,
) -> UserFacingError:
    technical = (detail or "").strip()
    if not technical or technical == TRANSIENT_DATA_MESSAGE:
        technical = "DATA_SOURCE_UNAVAILABLE: market data source returned no usable bars"
    return UserFacingError(
        TRANSIENT_DATA_CODE,
        TRANSIENT_DATA_MESSAGE,
        params=dict(params or {}),
        detail=technical,
    )


def _coded(
    code: str,
    message: str,
    *,
    params: dict[str, Any] | None = None,
    detail: str | None = None,
) -> UserFacingError:
    """Keep the code in the legacy sentence. The envelope carries code, params, and detail."""
    return UserFacingError(
        code,
        f"{message}（{code}）",
        params=dict(params or {}),
        detail=detail,
    )


def market_data_timeout(symbol_count: int) -> UserFacingError:
    return _coded(
        "MARKET_DATA_TIMEOUT",
        f"行情还没取完：{symbol_count} 只在限定时间内没有完成。请稍后重试。",
        params={"symbol_count": symbol_count},
        detail="TimeoutError: market data load exceeded the deadline",
    )


def market_data_rate_limited() -> UserFacingError:
    return _coded(
        "MARKET_DATA_RATE_LIMITED",
        "行情源限流（HTTP 429），多次退避后仍失败。请稍后重试。",
        detail="HTTP 429: rate limit retries exhausted",
    )


def market_data_fetch_failed(symbol: str) -> UserFacingError:
    return _coded(
        "MARKET_DATA_FETCH_FAILED",
        f"行情没有取到：{symbol}。",
        params={"symbol": symbol},
        detail=f"symbol fetch failed: {symbol}",
    )


def classify_load_failure(error: BaseException) -> UserFacingError | None:
    if isinstance(error, DataPipelineError):
        if error.code == TRANSIENT_DATA_CODE:
            return transient_data_error(detail=_technical(error))
        return UserFacingError(error.code, error.message, detail=_technical(error))
    if isinstance(error, UserFacingError):
        if error.detail:
            return error
        return UserFacingError(
            error.code,
            error.message,
            params=error.params,
            detail=_technical(error),
        )
    if isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code in {403, 429, 500, 502, 503, 504}:
            return transient_data_error(detail=_technical(error))
    if isinstance(error, (httpx.TimeoutException, httpx.ConnectError, TimeoutError, OSError)):
        return transient_data_error(detail=_technical(error))
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
        return transient_data_error(detail=_technical(error))
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
        raise transient_data_error(
            _EMPTY_FRAME_DETAIL,
            params={"symbols": len(symbols)},
        )
    if not symbols_with_any_bars(frame, symbols):
        raise transient_data_error(
            f"provider returned no bars for {len(symbols)} symbols",
            params={"symbols": len(symbols)},
        )
