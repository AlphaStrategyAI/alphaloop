"""Attach description mentions to a universe without inventing a default pool."""

from __future__ import annotations

from dataclasses import replace

from engine.research.models import DialogueRole, Research, Slot, Universe
from engine.research.symbol_identity import SymbolMention, extract_symbol_mentions


def described_mentions(research: Research) -> tuple[SymbolMention, ...]:
    """Symbols the user wrote. Assistant examples such as 「600519.SH」 are not included."""
    parts: list[str] = []
    if research.brief.thesis.value:
        parts.append(str(research.brief.thesis.value))
    for turn in research.dialogue:
        if turn.role is DialogueRole.USER:
            parts.append(turn.text)
    if not parts:
        return ()
    return extract_symbol_mentions("\n".join(parts))


def universe_with_mentions(universe: Universe, mentions: tuple[SymbolMention, ...]) -> Universe:
    resolved: list[str] = []
    seen: set[str] = set()
    unresolved: list[str] = []
    inferred: list[tuple[str, str]] = []
    for mention in mentions:
        if mention.canonical:
            if mention.canonical not in seen:
                resolved.append(mention.canonical)
                seen.add(mention.canonical)
            if mention.inferred:
                inferred.append((mention.raw, mention.canonical))
        else:
            unresolved.append(mention.raw)
    return replace(
        universe,
        symbols=tuple(resolved),
        symbol_list_version=None,
        user_symbols_override=True,
        unresolved_tokens=tuple(dict.fromkeys(unresolved)),
        inferred_symbols=tuple(inferred),
    )


def apply_described_symbols(research: Research) -> Research:
    """If the description names a symbol, do not leave the universe empty for the default pool."""
    universe = research.brief.universe.value
    if universe is None:
        return research
    if universe.user_symbols_override or universe.symbols or universe.unresolved_tokens:
        return research
    mentions = described_mentions(research)
    if not mentions:
        return research
    updated = universe_with_mentions(universe, mentions)
    brief = replace(research.brief, universe=Slot(updated, research.brief.universe.locked))
    return replace(research, brief=brief)
