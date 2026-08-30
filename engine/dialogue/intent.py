from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from engine.research.models import (
    AssetClass,
    CoverageFloor,
    Market,
    MethodRef,
    Research,
    Universe,
)


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
SLOT_WORDS = {
    "大致原理": "thesis",
    "资产类别": "universe",
    "最长有效研究时间": "max_effective_hours",
    "最长研究时间": "max_effective_hours",
    "第一轮": "round1_methods",
    "最低覆盖": "coverage_floor",
}


def _universe(message: str) -> Universe | None:
    market = Market.US if re.search(r"美股|美国|US", message, re.IGNORECASE) else None
    market = Market.CN if re.search(r"A股|中国|沪深|CN", message, re.IGNORECASE) else market
    asset = AssetClass.BOND if "债" in message else None
    asset = AssetClass.FUND if "基金" in message else asset
    asset = AssetClass.EQUITY if re.search(r"股|股票", message) else asset
    if market is None or asset is None:
        return None
    underlying = AssetClass.BOND if asset is AssetClass.FUND and "债" in message else asset
    if asset is AssetClass.FUND and underlying is AssetClass.FUND:
        return None
    return Universe(market, asset, underlying, ())


def interpret(message: str, research: Research) -> Intent:
    text = message.strip()
    if not text:
        return Intent(IntentKind.OFF_TOPIC, response="请输入与五项研究设定有关的信息。")
    unlocks = tuple(value for key, value in SLOT_WORDS.items() if key in text and "解锁" in text)
    if unlocks:
        return Intent(IntentKind.UNLOCK, unlocks=unlocks)
    locks = tuple(value for key, value in SLOT_WORDS.items() if key in text and "锁定" in text)
    updates: list[tuple[str, Any]] = []
    universe = _universe(text)
    if universe is not None:
        updates.append(("universe", universe))
        thesis = re.sub(r"我想|研究|锁定|并锁定", "", text).strip()
        if len(thesis) >= 4:
            updates.append(("thesis", thesis))
    hours = re.search(r"(\d+(?:\.\d+)?)\s*小时", text)
    if hours:
        value = float(hours.group(1))
        if not 0 < value <= 720:
            return Intent(IntentKind.OFF_TOPIC, response="有效研究时间必须大于0且不超过720小时。")
        updates.append(("max_effective_hours", value))
    methods = tuple(ref for word, ref in METHOD_WORDS.items() if word in text)
    if methods:
        updates.append(("round1_methods", methods))
    assets = re.search(r"至少\s*(\d+)\s*个", text)
    years = re.search(r"(\d+)\s*年", text)
    missing = re.search(r"缺失不超过\s*(\d+(?:\.\d+)?)\s*%", text)
    if assets and years and missing:
        updates.append(
            (
                "coverage_floor",
                CoverageFloor(
                    min_assets=int(assets.group(1)),
                    min_years=int(years.group(1)),
                    max_missing_pct=float(missing.group(1)),
                ),
            )
        )
    if updates or locks:
        return Intent(IntentKind.PROVIDE, tuple(updates), locks)
    return Intent(
        IntentKind.OFF_TOPIC,
        response="这条对话只用于完善五项研究设定，请回答当前研究问题。",
    )
