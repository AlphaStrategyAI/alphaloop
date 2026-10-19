"""User-visible strings added by A1. Kept in one place for the i18n pass."""

DATA_SOURCE_UNBOUND = "这项研究还没有可用的数据来源。"
FROZEN_INPUT_UNREADABLE = "这一版的冻结输入无法读取，已停止，不会改用其他数据。"
FROZEN_INPUT_MISSING = "这一版没有冻结输入，已停止，不会重新取数。"
DATA_WINDOW_UNPINNED = "这项研究没有钉住数据窗口。"
STRATEGY_FAMILY_NOT_RUNNABLE = "这一族还不能开跑。"
USER_SPECIFIED_LIST_NAME = "用户指定标的"
USER_OVERRIDE_NOTE = "已覆盖默认的池"
# strategy-families-v1 §4.5–§4.6: momentum, trend, and breakout are not a family row.
MOMENTUM_UNSUPPORTED_NOTICE = (
    "暂不支持。不推荐最接近的族，不推荐均值回归。动量是第二批首个新增族"
)


def version_segment(version: str) -> str:
    return f"版本 {version}"
