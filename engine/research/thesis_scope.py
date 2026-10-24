"""V1 executes mean reversion only. Other families are disclosed or blocked."""

from __future__ import annotations

import re

from engine.research.a1_copy import MOMENTUM_UNSUPPORTED_NOTICE
from engine.research.family_intent import classify_thesis

MEAN_REVERSION_ONLY_NOTICE = (
    "V1 只支持截面均值回归（反转）；你的论点会被记录但不会改变策略。要按均值回归继续吗？"
)
CONFIRM_CARD_NOTICE = "策略族：均值回归（V1 唯一）· 论点文字仅作记录，不改变策略"
# strategy-families-v1 §4.3 and §4.5. Shown only after the user names a supported family.
FAMILY_REPICK_NOTICE = "原述未采纳，方向与原话不同。相对你的原话，经济逻辑已改成这一族。"
FAMILY_FOLLOWUP = "没能对上已支持的策略族。可以说低波、股债再平衡、均值回归、基本面因子或全天候。"
MEAN_REVERSION_ACK_REQUIRED = "MEAN_REVERSION_ACK_REQUIRED"


def thesis_is_non_mean_reversion(text: str) -> bool:
    """True when the thesis names another family and does not name mean reversion.

    Momentum still counts when mean-reversion words are also present: the spec
    forbids treating momentum as mean reversion.
    """
    if not text:
        return False
    return classify_thesis(text).outcome in {"disclose", "block"}


def thesis_is_blocked_family(text: str | None) -> bool:
    """Momentum, trend, and breakout. These must not run."""
    return classify_thesis(text).outcome == "block"


_ACK = re.compile(
    r"(?:好的?|可以|确认|继续|是|要|按均值回归继续|就按均值回归继续|yes|yeah|yep|ok|okay)"
    r"[。！!？?\s]*",
    re.IGNORECASE,
)


def is_mean_reversion_ack(text: str) -> bool:
    """A bare yes, including 「按均值回归继续」. Not an explicit family choice."""
    return _ACK.fullmatch(text.strip()) is not None


def explicit_family_choice(text: str):
    """A supported family the user named. A yes-answer is not a choice."""
    if is_mean_reversion_ack(text):
        return None
    hit = classify_thesis(text)
    if hit.outcome in {"run", "disclose"}:
        return hit
    return None


def mean_reversion_only_notice(
    thesis: str | None,
    *,
    adopted: bool = False,
    repicked_family: str = "",
) -> str | None:
    """Display line only. Does not decide whether the thesis may run."""
    if repicked_family:
        return FAMILY_REPICK_NOTICE
    hit = classify_thesis(thesis)
    if hit.outcome == "block":
        return MOMENTUM_UNSUPPORTED_NOTICE
    if hit.outcome == "disclose":
        if not adopted:
            return MEAN_REVERSION_ONLY_NOTICE
        return CONFIRM_CARD_NOTICE
    return None


def export_thesis_markers(
    thesis: str | None,
    *,
    adopted: bool = False,
    repicked_family: str = "",
) -> dict[str, object]:
    markers: dict[str, object] = {
        "thesis_driven": False,
        "strategy_family": "mean_reversion",
    }
    notice = mean_reversion_only_notice(
        thesis,
        adopted=adopted,
        repicked_family=repicked_family,
    )
    if notice is not None:
        markers["mean_reversion_only_notice"] = notice
    return markers
