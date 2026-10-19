from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from engine.i18n.errors import build_error_envelope
from engine.research.data_errors import DataPipelineError
from engine.research.state_machine import InvalidTransition


class UserFacingError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        params: Mapping[str, Any] | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.params = dict(params or {})
        self.detail = detail


def classify_run_error(error: BaseException) -> tuple[str, str]:
    if isinstance(error, DataPipelineError):
        return error.code, error.message
    if isinstance(error, UserFacingError):
        return error.code, error.message
    text = str(error)
    if "prices must be non-empty" in text:
        return (
            "DATA_EMPTY_PRICES",
            "数据源未返回行情，请检查标的和网络。",
        )
    if "EmptySymbolsError" in text or "DATA_SYMBOLS_EMPTY" in text:
        return (
            "DATA_SYMBOLS_EMPTY",
            "未选择任何标的，无法加载行情。",
        )
    return ("RUN_LOOP_FAILED", text)


def http_error_payload(error: BaseException) -> dict[str, Any]:
    """Legacy ``error`` and ``code`` plus the I0 envelope fields ``params`` and ``detail``."""
    if isinstance(error, UserFacingError):
        return build_error_envelope(
            code=error.code,
            message=error.message,
            params=error.params,
            detail=error.detail,
        )
    if isinstance(error, InvalidTransition):
        message = str(error)
        code = "invalid_transition"
        if "running" in message.lower() and "modify" in message.lower():
            code = "RUNNING_CANNOT_MODIFY"
            message = "研究仍在运行中，请先暂停再确认修改。"
        return build_error_envelope(code=code, message=message)
    if isinstance(error, DataPipelineError):
        return build_error_envelope(code=error.code, message=error.message)
    return build_error_envelope(
        code="bad_request",
        message=str(error),
        detail=str(error),
    )
