"""Default symbol pool resolution for briefs without explicit tickers."""

from __future__ import annotations

from dataclasses import replace

from engine.research.models import Research, ResearchBrief, Slot, Universe
from engine.research.symbol_mentions import apply_described_symbols
from engine.research.symbol_pool import pool_for_market


def materialize_default_pool(research: Research) -> Research:
    """Fill empty universe.symbols from the versioned default pool when applicable.

    A description that names a symbol never receives this pool, even when the
    symbol could not be given an exchange suffix.
    """
    research = apply_described_symbols(research)
    universe = research.brief.universe.value
    if (
        universe is None
        or universe.user_symbols_override
        or universe.symbols
        or universe.unresolved_tokens
        or universe.symbol_asks
        or universe.market_mismatches
    ):
        return research
    pool = pool_for_market(
        universe.market,
        universe.asset_class,
        universe.underlying_asset_class,
    )
    if pool is None or not pool.symbols:
        return research
    updated = Universe(
        universe.market,
        universe.asset_class,
        universe.underlying_asset_class,
        pool.symbols,
        symbol_list_version=pool.version_id,
        user_symbols_override=False,
        ticker_hints=universe.ticker_hints,
        symbol_ask_answers=universe.symbol_ask_answers,
        unrecognized_tokens=universe.unrecognized_tokens,
        recognition_hidden=universe.recognition_hidden,
    )
    brief = replace(research.brief, universe=Slot(updated, True))
    return replace(
        research,
        brief=brief,
        symbol_list_version=pool.version_id,
    )


def pin_draft_data_source(research: Research) -> Research:
    """Leave the source unset. Yahoo and AkShare are not a default.

    The confirm card offers ``data_source_id_for_symbols`` as a choice. It is
    stored only after the user selects it. A running or finished research keeps
    the id it already has.
    """
    return research


def pool_resolvable_brief(brief: ResearchBrief) -> bool:
    universe = brief.universe.value
    if universe is None:
        return False
    if universe.unresolved_tokens or universe.symbol_asks or universe.market_mismatches:
        return False
    if universe.user_symbols_override:
        return bool(universe.symbols)
    if universe.symbols:
        return True
    pool = pool_for_market(
        universe.market,
        universe.asset_class,
        universe.underlying_asset_class,
    )
    return pool is not None and bool(pool.symbols)


def pool_resolvable(research: Research) -> bool:
    return pool_resolvable_brief(research.brief)
