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
    dismissed = {token.casefold() for token in research.dismissed_symbol_tokens}
    mentions = extract_symbol_mentions("\n".join(parts))
    if not dismissed:
        return mentions
    return tuple(
        mention
        for mention in mentions
        if mention.raw.casefold() not in dismissed
        and mention.raw.lstrip("$").casefold() not in dismissed
    )


def universe_with_mentions(universe: Universe, mentions: tuple[SymbolMention, ...]) -> Universe:
    resolved: list[str] = []
    seen: set[str] = set()
    unresolved: list[str] = []
    inferred: list[tuple[str, str]] = []
    asks: list[tuple[str, str]] = []
    hints: list[tuple[str, str]] = []
    for mention in mentions:
        if mention.kind == "hint" and mention.canonical:
            hints.append((mention.raw, mention.canonical))
            continue
        if mention.kind == "ask" and mention.canonical:
            asks.append((mention.raw, mention.canonical))
            continue
        if mention.canonical:
            if mention.canonical not in seen:
                resolved.append(mention.canonical)
                seen.add(mention.canonical)
            if mention.inferred:
                inferred.append((mention.raw, mention.canonical))
        else:
            unresolved.append(mention.raw)
    claimed = bool(resolved or unresolved or asks)
    return replace(
        universe,
        symbols=tuple(resolved),
        symbol_list_version=None if claimed else universe.symbol_list_version,
        user_symbols_override=claimed,
        unresolved_tokens=tuple(dict.fromkeys(unresolved)),
        inferred_symbols=tuple(inferred),
        symbol_asks=tuple(asks),
        ticker_hints=tuple(hints),
        recognition_hidden=False,
    )


def apply_described_symbols(research: Research) -> Research:
    """If the description names a symbol, do not leave the universe empty for the default pool."""
    universe = research.brief.universe.value
    if universe is None:
        return research
    if (
        universe.user_symbols_override
        or universe.symbols
        or universe.unresolved_tokens
        or universe.symbol_asks
    ):
        return research
    mentions = described_mentions(research)
    if not mentions:
        return research
    updated = universe_with_mentions(universe, mentions)
    brief = replace(research.brief, universe=Slot(updated, research.brief.universe.locked))
    return replace(research, brief=brief)
