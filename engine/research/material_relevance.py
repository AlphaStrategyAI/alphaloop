"""Deterministic relevance for Crossref papers.

A paper is relevant only when a strategy key term occurs in its title or
abstract. The score is fixed by where the term occurs. It is not a cutoff
tuned to a result set:

- 2 if any key term occurs in the title
- 1 if any key term occurs in the abstract and none occur in the title
- 0 otherwise

Relevant means score >= 1: at least one key term in the title or abstract.
Papers that score 0 are dropped. Nothing is added to fill a quota. An empty
list is the correct result when nothing matches.

Key terms come from a fixed lexicon, one group per detected family. The
family is the same classification the dialogue uses. Mean reversion's terms
are ``mean reversion``, ``mean-reversion``, ``mean reverting``, ``reversal``,
and ``均值回归``. Matching is case-insensitive. Hyphens and repeated spaces
are ignored, so ``mean-reversion`` matches ``mean reversion``.

When the query names no family, papers are kept as fetched. There is no
strategy term to require, so the filter does not empty the list. When it
names one or more families, a paper must match one of those families' terms.
Nothing is added to fill a quota.
"""

from __future__ import annotations

from typing import Protocol

from engine.research.family_intent import classify_thesis

_TERMS: dict[str, tuple[str, ...]] = {
    "mean_reversion": (
        "mean reversion",
        "mean-reversion",
        "mean reverting",
        "reversal",
        "均值回归",
    ),
    "low_volatility": (
        "low volatility",
        "low-volatility",
        "low vol",
        "低波",
        "低波动",
    ),
    "fundamental_factor": (
        "fundamental",
        "valuation",
        "value factor",
        "基本面",
        "估值",
        "价值",
    ),
    "stock_bond_rebalance": (
        "stock-bond",
        "rebalance",
        "60/40",
        "股债",
        "再平衡",
    ),
    "all_weather": (
        "all weather",
        "all-weather",
        "risk parity",
        "全天候",
    ),
    "momentum": (
        "momentum",
        "trend",
        "breakout",
        "动量",
        "趋势",
        "突破",
    ),
    "arbitrage": ("arbitrage", "套利"),
    "rotation": ("rotation", "轮动"),
    "growth": ("growth", "成长"),
}


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").replace("_", " ").split())


class _TextMaterial(Protocol):
    source: str
    title: str
    text: str


def _contains(haystack: str, term: str) -> bool:
    if not haystack or not term:
        return False
    return _normalize(term) in _normalize(haystack)


def strategy_key_terms(query: str) -> tuple[str, ...]:
    """Terms for the family the query names. Empty when it names none.

    Several disclose families keep the union of their terms. A paper then has
    to match one of those families, and unrelated papers still drop.
    """
    hit = classify_thesis(query)
    if hit.outcome == "none":
        return ()
    families = hit.families or (hit.family_id,)
    terms: list[str] = []
    for family_id in families:
        for term in _TERMS.get(family_id, ()):
            if term not in terms:
                terms.append(term)
    return tuple(terms)


def relevance_score(material: _TextMaterial, terms: tuple[str, ...]) -> int:
    """2 title, 1 abstract only, 0 no key term. See the module docstring."""
    if not terms:
        return 0
    title = material.title or ""
    abstract = material.text or ""
    if any(_contains(title, term) for term in terms):
        return 2
    if any(_contains(abstract, term) for term in terms):
        return 1
    return 0


def relevant_papers(materials: tuple[_TextMaterial, ...] | list[_TextMaterial], query: str):
    """Keep non-papers unchanged. Keep a paper only when its score is >= 1.

    A query that names no strategy group is returned unchanged.
    """
    terms = strategy_key_terms(query)
    if not terms:
        return tuple(materials)
    kept: list[_TextMaterial] = []
    for item in materials:
        if item.source != "papers":
            kept.append(item)
            continue
        if relevance_score(item, terms) >= 1:
            kept.append(item)
    return tuple(kept)
