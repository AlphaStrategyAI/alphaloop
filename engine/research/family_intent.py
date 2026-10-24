"""Closed lexicon for strategy-family intent.

A thesis maps to one explicit outcome. There is no silent fallback onto mean
reversion.

Outcomes:

- ``run``: the thesis is mean reversion, which the engine executes.
- ``disclose``: a known family the engine does not execute yet. The confirm
  card states that mean reversion is what will actually run (the low-vol path).
- ``block``: momentum, trend, or breakout. The spec says these must not run.
- ``none``: no family keyword. The dialogue asks again instead of guessing.

Mean-reversion keywords win over a disclose keyword, so ``低波动量价回归`` stays
mean reversion. Momentum keywords win over mean reversion: the spec forbids
folding momentum into mean reversion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_Outcome = str  # "run" | "disclose" | "block" | "none"


@dataclass(frozen=True, slots=True)
class FamilyHit:
    """One classification. ``families`` lists every disclose id that matched."""

    family_id: str
    outcome: _Outcome
    families: tuple[str, ...] = ()


def _latin(text: str, phrase: str) -> bool:
    """Case-insensitive phrase match. Hyphens and spaces are the same."""
    pattern = re.escape(phrase.lower()).replace(r"\-", r"[\s\-]+").replace(r"\ ", r"[\s\-]+")
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text.lower()) is not None


def _any_zh(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _any_en(text: str, words: tuple[str, ...]) -> bool:
    return any(_latin(text, word) for word in words)


# Existing non-mean-reversion table, plus the keywords it was missing
# (基本面 / 股债 / 全天候) and the English names of the same families.
# ``波动量`` contains the characters 动量. That phrase is low-vol, not momentum.
_MOMENTUM_ZH = re.compile(r"(?<!波)动量|趋势|突破")
_MOMENTUM_EN = ("momentum", "trend", "breakout")

_MEAN_ZH = ("均值", "回归", "反转")
_MEAN_EN = ("mean reversion", "mean-reversion", "reversal")

# (family id, zh keywords, en keywords). First matching id is the literature family
# when several disclose families match; the outcome is still disclose, not a guess
# about which family will execute.
_DISCLOSE: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "fundamental_factor",
        ("基本面", "多因子", "因子", "估值", "价值"),
        ("fundamental", "multi-factor", "multifactor", "factor", "valuation", "value"),
    ),
    (
        "stock_bond_rebalance",
        ("股债", "再平衡"),
        ("stock-bond", "stock bond", "rebalance", "rebalancing"),
    ),
    ("all_weather", ("全天候",), ("all-weather", "all weather")),
    ("low_volatility", ("低波",), ("low-volatility", "low volatility", "low vol")),
    ("arbitrage", ("套利",), ("arbitrage",)),
    ("rotation", ("轮动",), ("rotation",)),
    ("growth", ("成长",), ("growth",)),
)

_SIXTY_FORTY = re.compile(r"60\s*[/／]\s*40")


def _disclose_hits(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for family_id, zh_words, en_words in _DISCLOSE:
        if _any_zh(text, zh_words) or _any_en(text, en_words):
            found.append(family_id)
    if _SIXTY_FORTY.search(text) and "stock_bond_rebalance" not in found:
        found.append("stock_bond_rebalance")
    return tuple(found)


def _momentum(text: str) -> bool:
    return _MOMENTUM_ZH.search(text) is not None or _any_en(text, _MOMENTUM_EN)


def _mean_reversion(text: str) -> bool:
    return _any_zh(text, _MEAN_ZH) or _any_en(text, _MEAN_EN)


def classify_thesis(text: str | None) -> FamilyHit:
    """Classify ``text``. Empty and unrecognized theses are ``none``."""
    raw = text or ""
    if not raw.strip():
        return FamilyHit("none", "none")
    if _momentum(raw):
        return FamilyHit("momentum", "block", ("momentum",))
    disclose = _disclose_hits(raw)
    if _mean_reversion(raw) and not disclose:
        return FamilyHit("mean_reversion", "run", ("mean_reversion",))
    if _mean_reversion(raw) and disclose:
        # A mean-reversion word keeps the V1 family. ``低波动量价回归`` is this case.
        return FamilyHit("mean_reversion", "run", ("mean_reversion",))
    if len(disclose) == 1:
        return FamilyHit(disclose[0], "disclose", disclose)
    if len(disclose) > 1:
        return FamilyHit(disclose[0], "disclose", disclose)
    return FamilyHit("none", "none")


def thesis_mentions_strategy(text: str | None) -> bool:
    """True when the text names a family, including mean reversion."""
    return classify_thesis(text).outcome != "none"
