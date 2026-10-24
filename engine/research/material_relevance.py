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

Key terms come from a fixed lexicon. A query selects a group when it contains
any trigger for that group (a phrase, or the family id). Mean reversion's
terms are ``mean reversion``, ``mean-reversion``, ``mean reverting``,
``reversal``, and ``均值回归``. Matching is case-insensitive. Hyphens and
repeated spaces are ignored, so ``mean-reversion`` matches ``mean reversion``.

When the query names no group, papers are kept as fetched. There is no
strategy term to require, so the filter does not empty the list.
"""

from __future__ import annotations

from typing import Protocol

_MEAN_REVERSION_TERMS = (
    "mean reversion",
    "mean-reversion",
    "mean reverting",
    "reversal",
    "均值回归",
)
_MEAN_REVERSION_TRIGGERS = _MEAN_REVERSION_TERMS + (
    "mean_reversion",
    "legacy_mean_reversion",
)


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
    """Terms the query names. Empty when the query names no known strategy."""
    folded = _normalize(query or "")
    raw = query or ""
    for trigger in _MEAN_REVERSION_TRIGGERS:
        if trigger in raw or _normalize(trigger) in folded:
            return _MEAN_REVERSION_TERMS
    return ()


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
