from __future__ import annotations

from engine.research.data_errors import DataPipelineError
from engine.research.state_machine import InvalidTransition


class UserFacingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


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


def http_error_payload(error: BaseException) -> dict[str, str]:
    if isinstance(error, UserFacingError):
        return {"error": error.message, "code": error.code}
    if isinstance(error, InvalidTransition):
        message = str(error)
        code = "invalid_transition"
        if "running" in message.lower() and "modify" in message.lower():
            code = "RUNNING_CANNOT_MODIFY"
            message = "研究仍在运行中，请先暂停再确认修改。"
        return {"error": message, "code": code}
    if isinstance(error, DataPipelineError):
        return {"error": error.message, "code": error.code}
    return {"error": str(error), "code": "bad_request"}
