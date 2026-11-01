from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from engine.dialogue.prompts import QUESTIONS, SlotName
from engine.research.coverage_parse import merge_coverage_floor
from engine.research.family_intent import classify_thesis, thesis_mentions_strategy
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


APOLOGY_PREFIX = "没能理解你的意思。"

# Chinese catalog names, the older dialogue aliases, and the English prompt
# examples. Matching is case-insensitive; hyphens and spaces are the same.
_METHOD_PHRASES: tuple[tuple[str, MethodRef], ...] = (
    ("分段稳健性检验", MethodRef("overfit.walk", "walk-v1")),
    ("走样检验", MethodRef("overfit.walk", "walk-v1")),
    ("subperiod robustness check", MethodRef("overfit.walk", "walk-v1")),
    ("样本外稳定", MethodRef("stability.oos", "stability-v1")),
    ("out-of-sample stability", MethodRef("stability.oos", "stability-v1")),
    ("集中度", MethodRef("crowding.load", "crowding-v1")),
    ("拥挤度", MethodRef("crowding.load", "crowding-v1")),
    ("concentration", MethodRef("crowding.load", "crowding-v1")),
    ("换手成本", MethodRef("cost.turnover", "cost-v1")),
    ("turnover cost", MethodRef("cost.turnover", "cost-v1")),
)


def _cn_mention(mention: object) -> bool:
    raw = getattr(mention, "raw", "")
    canonical = getattr(mention, "canonical", None) or ""
    if re.fullmatch(r"\d{6}(?:\.[A-Za-z]{2})?", raw):
        return True
    return canonical.endswith((".SH", ".SZ", ".BJ"))


_CN_MARKET = re.compile(r"A\s*股|中国|沪深|China|\bCN\b", re.IGNORECASE)
_US_MARKET = re.compile(r"美股|美国|\bUS\b", re.IGNORECASE)
_BARE_STRATEGY = re.compile(r"volatility|squeeze|策略", re.IGNORECASE)
_US_FAMILY_BASKETS = {
    "stock_bond_rebalance": ("SPY", "AGG"),
    "all_weather": ("SPY", "TLT", "IEF", "GLD", "DBC"),
}


def _named_market(message: str) -> Market | None:
    if _CN_MARKET.search(message):
        return Market.CN
    if _US_MARKET.search(message):
        return Market.US
    return None


def _us_family_basket(message: str) -> Universe | None:
    """Stock-bond and all-weather with no China market lock the US fund baskets."""
    hit = classify_thesis(message)
    symbols = _US_FAMILY_BASKETS.get(hit.family_id)
    if symbols is None or hit.outcome != "disclose":
        return None
    if _CN_MARKET.search(message):
        return None
    mentions = extract_symbol_mentions(message)
    if any(_cn_mention(mention) for mention in mentions):
        return None
    named = tuple(
        mention.canonical
        for mention in mentions
        if mention.kind == "symbol" and mention.canonical and not _cn_mention(mention)
    )
    return Universe(
        Market.US,
        AssetClass.FUND,
        AssetClass.EQUITY,
        named or symbols,
        user_symbols_override=True,
    )


def _parse_universe(message: str) -> Universe | None:
    market = _named_market(message)
    if re.search(r"基金|ETF", message, re.IGNORECASE):
        asset = AssetClass.FUND
        underlying = AssetClass.BOND if "债" in message else AssetClass.EQUITY
    elif "债" in message and classify_thesis(message).family_id != "stock_bond_rebalance":
        asset = AssetClass.BOND
        underlying = AssetClass.BOND
    elif re.search(r"股|股票|stocks|equities|equity", message, re.IGNORECASE):
        asset = AssetClass.EQUITY
        underlying = AssetClass.EQUITY
    elif thesis_mentions_strategy(message):
        # A named family with a market and no asset word still has a universe.
        # The card says which strategy will actually run.
        asset = AssetClass.EQUITY
        underlying = AssetClass.EQUITY
    else:
        asset = None
        underlying = None
    mentions = extract_symbol_mentions(message)
    if market is None and any(_cn_mention(mention) for mention in mentions):
        market = Market.CN
    if market is None and any(
        mention.canonical and not _cn_mention(mention) for mention in mentions
    ):
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
    found: list[tuple[int, float]] = []
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*分钟", message):
        found.append((match.start(), float(match.group(1)) / 60.0))
    for match in re.finditer(
        r"(\d+(?:\.\d+)?)\s*(?:minutes?|mins?)\b",
        message,
        re.IGNORECASE,
    ):
        found.append((match.start(), float(match.group(1)) / 60.0))
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*小时", message):
        found.append((match.start(), float(match.group(1))))
    for match in re.finditer(
        r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b",
        message,
        re.IGNORECASE,
    ):
        found.append((match.start(), float(match.group(1))))
    if found:
        value = min(found, key=lambda item: item[0])[1]
    elif re.search(r"半小时", message) or re.search(
        r"\bhalf\s+(?:an?\s+)?hour\b",
        message,
        re.IGNORECASE,
    ):
        value = 0.5
    else:
        return None
    if not 0 < value <= 720:
        return None
    return value


def _parse_coverage(message: str, current: CoverageFloor | None = None) -> CoverageFloor | None:
    return merge_coverage_floor(message, current)


def _phrase_in(text: str, phrase: str) -> bool:
    pattern = re.escape(phrase.casefold())
    pattern = pattern.replace(r"\-", r"[\s\-]+").replace(r"\ ", r"[\s\-]+")
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text.casefold()) is not None


def _parse_methods(message: str) -> tuple[MethodRef, ...]:
    methods: list[MethodRef] = []
    seen: set[str] = set()
    for phrase, ref in _METHOD_PHRASES:
        if _phrase_in(message, phrase) and ref.method_id not in seen:
            methods.append(ref)
            seen.add(ref.method_id)
    return tuple(methods)


_STRATEGY_HINT = re.compile(
    r"均值|回归|动量|套利|波动|多空|轮动|价值|成长|利差|收缩|修复|量价"
    r"|基本面|因子|估值|股债|再平衡|全天候|低波|趋势|突破"
    r"|momentum|trend|breakout|fundamental|factor|valuation|rebalance"
    r"|all[\s\-]*weather|low[\s\-]*vol|mean[\s\-]*reversion|reversal|arbitrage|growth"
    r"|60\s*[/／]\s*40",
    re.IGNORECASE,
)
_MARKET_HINT = re.compile(r"美股|美国|A\s*股|中国|沪深|股|债|基金|ETF", re.IGNORECASE)


def _thesis_acceptable(message: str) -> bool:
    if _parse_universe(message) is not None:
        return True
    # A strategy with no named market is still a thesis. The card asks which
    # market's default pool to use. Nothing is preselected.
    if _STRATEGY_HINT.search(message) is not None:
        return True
    if thesis_mentions_strategy(message):
        return True
    # A market plus strategy language outside the closed lexicon is still a thesis.
    # The dialogue asks which family instead of the generic misunderstanding.
    return _named_market(message) is not None and _BARE_STRATEGY.search(message) is not None


def _universe_for_thesis(text: str) -> Universe | None:
    basket = _us_family_basket(text)
    if basket is not None:
        return basket
    parsed = _parse_universe(text)
    if parsed is not None:
        return parsed
    if _STRATEGY_HINT.search(text) is None and not thesis_mentions_strategy(text):
        return None
    blank = Universe(
        Market.CN,
        AssetClass.EQUITY,
        AssetClass.EQUITY,
        (),
        market_unspecified=True,
    )
    mentions = extract_symbol_mentions(text)
    if not mentions:
        return blank
    return universe_with_mentions(blank, mentions)


def _parse_thesis(message: str) -> str | None:
    text = message.strip()
    # 全天候 is three characters and is still a thesis. Other fragments stay rejected.
    if len(text) < 4 and not thesis_mentions_strategy(text):
        return None
    if not text or not _thesis_acceptable(text):
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
        universe = (
            _universe_for_thesis(text) if "thesis" not in brief_filled else _parse_universe(text)
        )
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


_HOUR_WORDS = {
    "一": 1.0,
    "二": 2.0,
    "两": 2.0,
    "三": 3.0,
    "四": 4.0,
    "五": 5.0,
    "六": 6.0,
    "七": 7.0,
    "八": 8.0,
    "九": 9.0,
    "十": 10.0,
    "十二": 12.0,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
    "twelve": 12.0,
}
_HOUR_TOKEN = re.compile(
    r"(十二|十|[一二两三四五六七八九]|\d+(?:\.\d+)?)\s*小时"
    r"|半\s*小时"
    r"|(one|two|three|four|five|six|seven|eight|nine|ten|twelve|\d+(?:\.\d+)?)"
    r"\s*(?:hours?|hrs?)\b"
    r"|\bhalf\s+(?:an?\s+)?hour\b",
    re.IGNORECASE,
)
_CORRECTION = re.compile(
    r"改为|改成|改回|其他照旧|leave the rest|change the|change it to",
    re.IGNORECASE,
)
_RETRACT = re.compile(r"撤回|撤销|\bundo\b", re.IGNORECASE)


def hour_mentions(message: str) -> tuple[float, ...]:
    """Hour values in reading order, including 六小时 / six hours."""
    found: list[float] = []
    for match in _HOUR_TOKEN.finditer(message):
        token = next((group for group in match.groups() if group), "")
        if not token:
            if "半" in match.group(0) or "half" in match.group(0).lower():
                found.append(0.5)
            continue
        if token in _HOUR_WORDS:
            found.append(_HOUR_WORDS[token])
            continue
        lowered = token.lower()
        if lowered in _HOUR_WORDS:
            found.append(_HOUR_WORDS[lowered])
            continue
        try:
            found.append(float(token))
        except ValueError:
            continue
    return tuple(found)


def is_hour_correction(message: str) -> bool:
    return _CORRECTION.search(message) is not None


def hour_correction_conflict(message: str, research: Research) -> bool:
    """The quoted old duration is not the one currently stored."""
    if not is_hour_correction(message):
        return False
    mentions = hour_mentions(message)
    if len(mentions) < 2:
        return False
    current = research.brief.max_effective_hours.value
    if not isinstance(current, (int, float)):
        return False
    return abs(float(current) - mentions[0]) > 1e-9


def correction_updates(message: str, research: Research) -> tuple[tuple[str, Any], ...]:
    """Explicit revisions apply even when the slot is already filled.

    ``其他照旧`` does not invent values for the slots the sentence leaves alone.
    A quoted old duration that does not match the stored one is not applied.
    """
    if not is_hour_correction(message) or hour_correction_conflict(message, research):
        return ()
    mentions = hour_mentions(message)
    if not mentions:
        return ()
    value = mentions[-1]
    if not 0 < value <= 720:
        return ()
    current = research.brief.max_effective_hours.value
    if isinstance(current, (int, float)) and abs(float(current) - value) < 1e-9:
        return ()
    return (("max_effective_hours", value),)


def retract_slots(message: str, research: Research) -> tuple[str, ...]:
    """Named withdrawals. A bare 撤回 drops the last filled slot."""
    if _CORRECTION.search(message) or _RETRACT.search(message) is None:
        return ()
    found: list[str] = []
    if re.search(r"时长|时间|hours?", message, re.IGNORECASE):
        found.append("max_effective_hours")
    if re.search(r"论点|原理|thesis", message, re.IGNORECASE):
        found.append("thesis")
    if re.search(r"标的|市场|universe|market", message, re.IGNORECASE):
        found.append("universe")
    if re.search(r"方法|methods?", message, re.IGNORECASE):
        found.append("round1_methods")
    if re.search(r"覆盖|coverage", message, re.IGNORECASE):
        found.append("coverage_floor")
    if found:
        return tuple(dict.fromkeys(found))
    if not re.fullmatch(r"(?:请)?(?:撤回|撤销|undo)[。！!？?\s]*", message.strip(), re.IGNORECASE):
        return ()
    for name in (
        "coverage_floor",
        "round1_methods",
        "max_effective_hours",
        "universe",
        "thesis",
    ):
        if getattr(research.brief, name).value is not None:
            return (name,)
    return ()


def interpret(
    message: str,
    research: Research,
    active_slot: SlotName | None,
) -> Intent:
    text = message.strip()
    if not text:
        prompt = (
            QUESTIONS.get(active_slot, "请输入与五项研究设定有关的信息。") if active_slot else ""
        )
        return Intent(IntentKind.OFF_TOPIC, response=prompt or "请输入与五项研究设定有关的信息。")
    if "解锁" in text:
        return Intent(IntentKind.OFF_TOPIC, response="在确认开跑卡上点「改一改」即可调整单项设定。")
    retracted = retract_slots(text, research)
    if retracted:
        return Intent(IntentKind.UNLOCK, unlocks=retracted)

    brief = research.brief
    filled = {
        name
        for name in (
            "thesis",
            "universe",
            "max_effective_hours",
            "round1_methods",
            "coverage_floor",
        )
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

    for name, value in correction_updates(text, research):
        unique = [(slot_name, slot_value) for slot_name, slot_value in unique if slot_name != name]
        unique.append((name, value))

    if unique:
        return Intent(IntentKind.PROVIDE, tuple(unique))

    if active_slot is not None:
        return Intent(
            IntentKind.OFF_TOPIC,
            response=(f"{APOLOGY_PREFIX}{QUESTIONS[active_slot]}"),
        )
    return Intent(
        IntentKind.OFF_TOPIC,
        response=EMPTY_POOL_DIALOGUE_PROMPT,
    )
