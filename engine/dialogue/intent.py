from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from engine.dialogue.prompts import QUESTIONS, SlotName
from engine.research.models import (
    AssetClass,
    CoverageFloor,
    Market,
    MethodRef,
    Research,
    Universe,
)
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
    "走样检验": MethodRef("overfit.walk", "walk-v1"),
    "样本外稳定": MethodRef("stability.oos", "stability-v1"),
    "拥挤度": MethodRef("crowding.load", "crowding-v1"),
    "换手成本": MethodRef("cost.turnover", "cost-v1"),
}


def _extract_tickers(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for token in re.split(r"[、,，\s]+", text):
        token = token.strip().upper()
        if re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", token):
            found.append(token)
    return tuple(dict.fromkeys(found))


def _parse_universe(message: str) -> Universe | None:
    market = Market.US if re.search(r"美股|美国|US", message, re.IGNORECASE) else None
    market = Market.CN if re.search(r"A股|中国|沪深|CN", message, re.IGNORECASE) else market
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
    if market is None or asset is None or underlying is None:
        return None
    tickers = _extract_tickers(message)
    if tickers:
        return Universe(
            market,
            asset,
            underlying,
            tickers,
            user_symbols_override=True,
        )
    return Universe(market, asset, underlying, ())


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


def _parse_coverage(message: str) -> CoverageFloor | None:
    assets = re.search(r"至少\s*(\d+)\s*个", message)
    years = re.search(r"(\d+)\s*年", message)
    missing = re.search(r"缺失不超过\s*(\d+(?:\.\d+)?)\s*%", message)
    if assets and years and missing:
        return CoverageFloor(
            min_assets=int(assets.group(1)),
            min_years=int(years.group(1)),
            max_missing_pct=float(missing.group(1)),
        )
    return None


def _parse_methods(message: str) -> tuple[MethodRef, ...]:
    methods = tuple(ref for word, ref in METHOD_WORDS.items() if word in message)
    return methods


def _parse_thesis(message: str) -> str | None:
    text = message.strip()
    if len(text) < 4:
        return None
    return text


def _fill_slot(active: SlotName, text: str) -> list[tuple[str, Any]]:
    updates: list[tuple[str, Any]] = []
    if active is SlotName.THESIS:
        thesis = _parse_thesis(text)
        if thesis:
            updates.append(("thesis", thesis))
        universe = _parse_universe(text)
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
        floor = _parse_coverage(text)
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
        universe = _parse_universe(text)
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
        floor = _parse_coverage(text)
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
        return Intent(IntentKind.OFF_TOPIC, response=QUESTIONS[active_slot])
    return Intent(
        IntentKind.OFF_TOPIC,
        response=EMPTY_POOL_DIALOGUE_PROMPT,
    )
