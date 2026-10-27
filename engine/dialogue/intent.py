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
