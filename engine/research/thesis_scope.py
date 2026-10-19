"""V1 executes mean reversion only. Non-mean-reversion theses are recorded, not driven."""

from __future__ import annotations

import re

MEAN_REVERSION_ONLY_NOTICE = (
    "V1 只支持截面均值回归（反转）；你的论点会被记录但不会改变策略。要按均值回归继续吗？"
)
CONFIRM_CARD_NOTICE = "策略族：均值回归（V1 唯一）· 论点文字仅作记录，不改变策略"

_NON_MEAN_REVERSION = re.compile(r"动量|趋势|突破|多因子|低波|套利|轮动|价值|成长")
_MEAN_REVERSION = re.compile(r"均值|回归|反转")
_ACK = re.compile(
    r"(?:好的?|可以|确认|继续|是|要|按均值回归继续|就按均值回归继续)[。！!？?]*"
)


def thesis_is_non_mean_reversion(text: str) -> bool:
    """True when the thesis names another family and does not name mean reversion."""
    if not text:
        return False
    return _NON_MEAN_REVERSION.search(text) is not None and _MEAN_REVERSION.search(text) is None


def is_mean_reversion_ack(text: str) -> bool:
    return _ACK.fullmatch(text.strip()) is not None


def mean_reversion_only_notice(thesis: str | None) -> str | None:
    if thesis and thesis_is_non_mean_reversion(thesis):
        return CONFIRM_CARD_NOTICE
    return None


def export_thesis_markers(thesis: str | None) -> dict[str, object]:
    markers: dict[str, object] = {
        "thesis_driven": False,
        "strategy_family": "mean_reversion",
    }
    notice = mean_reversion_only_notice(thesis)
    if notice is not None:
        markers["mean_reversion_only_notice"] = notice
    return markers
