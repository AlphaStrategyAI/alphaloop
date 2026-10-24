from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from engine.dialogue.prompts import QUESTIONS, SlotName
from engine.research.coverage_parse import merge_coverage_floor
from engine.research.models import (
    AssetClass,
    CoverageFloor,
    Market,
    MethodRef,
    Research,
    Universe,
)
from engine.research.symbol_identity import extract_symbol_mentions
from engine.research.symbol_mentions import universe_with_mentions
from engine.research.symbol_pool import EMPTY_POOL_DIALOGUE_PROMPT


class IntentKind(StrEnum):
    PROVIDE = "provide"
    LOCK = "lock"
    UNLOCK = "unlock"
    OFF_TOPIC = "off_topic"


@dataclass(frozen=True, slots=True)
class Intent:
    kind: IntentKind
    updates: tuple[tuple[str, Any], ...] = ()
    locks: tuple[str, ...] = ()
    unlocks: tuple[str, ...] = ()
    response: str = ""


METHOD_WORDS = {
    "分段稳健性检验": MethodRef("overfit.walk", "walk-v1"),
    "走样检验": MethodRef("overfit.walk", "walk-v1"),
    "样本外稳定": MethodRef("stability.oos", "stability-v1"),
    "集中度": MethodRef("crowding.load", "crowding-v1"),
    "拥挤度": MethodRef("crowding.load", "crowding-v1"),
    "换手成本": MethodRef("cost.turnover", "cost-v1"),
}


def _cn_mention(mention: object) -> bool:
    raw = getattr(mention, "raw", "")
    canonical = getattr(mention, "canonical", None) or ""
    if re.fullmatch(r"\d{6}(?:\.[A-Za-z]{2})?", raw):
        return True
    return canonical.endswith((".SH", ".SZ", ".BJ"))


def _parse_universe(message: str) -> Universe | None:
    market = Market.US if re.search(r"美股|美国|US", message, re.IGNORECASE) else None
    market = Market.CN if re.search(r"A\s*股|中国|沪深|CN", message, re.IGNORECASE) else market
    if re.search(r"基金|ETF", message, re.IGNORECASE):
        asset = AssetClass.FUND
        underlying = AssetClass.BOND if "债" in message else AssetClass.EQUITY
    elif "债" in message:
        asset = AssetClass.BOND
        underlying = AssetClass.BOND
    elif re.search(r"股|股票", message):
        asset = AssetClass.EQUITY
        underlying = AssetClass.EQUITY
    else:
        asset = None
        underlying = None
    mentions = extract_symbol_mentions(message)
    if market is None and any(_cn_mention(mention) for mention in mentions):
        market = Market.CN
    if market is None and any(mention.canonical and not _cn_mention(mention) for mention in mentions):
        market = Market.US
    if asset is None and mentions:
        asset = AssetClass.EQUITY
        underlying = AssetClass.EQUITY
    if market is None or asset is None or underlying is None:
        return None
    blank = Universe(market, asset, underlying, ())
    if mentions:
        return universe_with_mentions(blank, mentions)
    return blank


def _parse_hours(message: str) -> float | None:
    if re.search(r"半小时", message):
        return 0.5
    minutes = re.search(r"(\d+(?:\.\d+)?)\s*分钟", message)
    if minutes:
        value = float(minutes.group(1)) / 60.0
        if not 0 < value <= 720:
            return None
        return value
    hours = re.search(r"(\d+(?:\.\d+)?)\s*小时", message)
    if hours:
        value = float(hours.group(1))
        if not 0 < value <= 720:
            return None
        return value
    return None


def _parse_coverage(message: str, current: CoverageFloor | None = None) -> CoverageFloor | None:
    return merge_coverage_floor(message, current)


def _parse_methods(message: str) -> tuple[MethodRef, ...]:
    methods: list[MethodRef] = []
    seen: set[str] = set()
    for word, ref in METHOD_WORDS.items():
        if word in message and ref.method_id not in seen:
            methods.append(ref)
            seen.add(ref.method_id)
    return tuple(methods)


_STRATEGY_HINT = re.compile(
    r"均值|回归|动量|套利|波动|多空|轮动|价值|成长|利差|收缩|修复|量价"
)
_MARKET_HINT = re.compile(r"美股|美国|A\s*股|中国|沪深|股|债|基金|ETF", re.IGNORECASE)


def _thesis_acceptable(message: str) -> bool:
    if _parse_universe(message) is not None:
        return True
    # A strategy with no named market is still a thesis. The universe stays
    # the default China A-share equity pool. Indicator words do not set a market.
    return _STRATEGY_HINT.search(message) is not None


def _universe_for_thesis(text: str) -> Universe | None:
    parsed = _parse_universe(text)
    if parsed is not None:
        return parsed
    if _STRATEGY_HINT.search(text) is None:
        return None
    blank = Universe(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY, ())
    mentions = extract_symbol_mentions(text)
    if not mentions:
        return blank
    return universe_with_mentions(blank, mentions)


def _parse_thesis(message: str) -> str | None:
    text = message.strip()
    if len(text) < 4 or not _thesis_acceptable(text):
        return None
    return text


def _fill_slot(active: SlotName, text: str) -> list[tuple[str, Any]]:
    updates: list[tuple[str, Any]] = []
    if active is SlotName.THESIS:
        thesis = _parse_thesis(text)
        if thesis:
            updates.append(("thesis", thesis))
        universe = _universe_for_thesis(text)
        if universe is not None:
            updates.append(("universe", universe))
    elif active is SlotName.UNIVERSE:
        universe = _parse_universe(text)
        if universe is not None:
            updates.append(("universe", universe))
    elif active is SlotName.MAX_EFFECTIVE_HOURS:
        hours = _parse_hours(text)
        if hours is not None:
            updates.append(("max_effective_hours", hours))
    elif active is SlotName.ROUND1_METHODS:
        methods = _parse_methods(text)
        if methods:
            updates.append(("round1_methods", methods))
    elif active is SlotName.COVERAGE_FLOOR:
        floor = _parse_coverage(text, None)
        if floor is not None:
            updates.append(("coverage_floor", floor))
    return updates


def _extras_from_any_slot(text: str, brief_filled: set[str]) -> list[tuple[str, Any]]:
    extras: list[tuple[str, Any]] = []
    if "thesis" not in brief_filled:
        thesis = _parse_thesis(text)
        if thesis and _parse_universe(text) is None:
            pass
    if "universe" not in brief_filled:
        universe = _universe_for_thesis(text) if "thesis" not in brief_filled else _parse_universe(text)
        if universe is not None:
            extras.append(("universe", universe))
    if "max_effective_hours" not in brief_filled:
        hours = _parse_hours(text)
        if hours is not None:
            extras.append(("max_effective_hours", hours))
    if "round1_methods" not in brief_filled:
        methods = _parse_methods(text)
        if methods:
            extras.append(("round1_methods", methods))
    if "coverage_floor" not in brief_filled:
        floor = _parse_coverage(text, None)
        if floor is not None:
            extras.append(("coverage_floor", floor))
    if "thesis" not in brief_filled:
        thesis = _parse_thesis(text)
        if thesis:
            extras.append(("thesis", thesis))
    return extras


def interpret(
    message: str,
    research: Research,
    active_slot: SlotName | None,
) -> Intent:
    text = message.strip()
    if not text:
        prompt = QUESTIONS.get(active_slot, "请输入与五项研究设定有关的信息。") if active_slot else ""
        return Intent(IntentKind.OFF_TOPIC, response=prompt or "请输入与五项研究设定有关的信息。")
    if "解锁" in text:
        return Intent(IntentKind.OFF_TOPIC, response="在确认开跑卡上点「改一改」即可调整单项设定。")

    brief = research.brief
    filled = {
        name
        for name in ("thesis", "universe", "max_effective_hours", "round1_methods", "coverage_floor")
        if getattr(brief, name).value is not None
    }

    updates: list[tuple[str, Any]] = []
    if active_slot is not None:
        updates.extend(_fill_slot(active_slot, text))
    updates.extend(_extras_from_any_slot(text, filled))
    # de-dupe by slot name, first wins
    seen: set[str] = set()
    unique: list[tuple[str, Any]] = []
    for name, value in updates:
        if name in seen:
            continue
        seen.add(name)
        unique.append((name, value))

    if unique:
        return Intent(IntentKind.PROVIDE, tuple(unique))

    if active_slot is not None:
        return Intent(
            IntentKind.OFF_TOPIC,
            response=(
                f"没能理解你的意思。{QUESTIONS[active_slot]}"
            ),
        )
    return Intent(
        IntentKind.OFF_TOPIC,
        response=EMPTY_POOL_DIALOGUE_PROMPT,
    )
