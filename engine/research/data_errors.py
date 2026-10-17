from __future__ import annotations


class DataPipelineError(Exception):
    """User-facing data error with a stable machine code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class EmptySymbolsError(DataPipelineError):
    def __init__(self) -> None:
        super().__init__(
            "DATA_SYMBOLS_EMPTY",
            "未选择任何标的，无法加载行情。请在确认开跑前锁定具体代码。",
        )
