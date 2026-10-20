"""Default symbol pool resolution for briefs without explicit tickers."""

from __future__ import annotations

from dataclasses import replace

from engine.research.models import Research, ResearchBrief, ResearchStatus, Slot, Universe
from engine.research.planned_data_window import data_source_id_for_symbols
from engine.research.symbol_pool import pool_for_market


def materialize_default_pool(research: Research) -> Research:
    """Fill empty universe.symbols from the versioned default pool when applicable."""
    universe = research.brief.universe.value
    if universe is None or universe.user_symbols_override or universe.symbols:
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
    )
    brief = replace(research.brief, universe=Slot(updated, True))
    return replace(
        research,
        brief=brief,
        symbol_list_version=pool.version_id,
    )


def pin_draft_data_source(research: Research) -> Research:
    """Store the same source id the confirm card will display.

    Only drafts change. A running or finished research keeps the id it pinned
    when it started, so an old record does not get a new source on open.
    """
    if research.status is not ResearchStatus.DRAFT:
        return research
    universe = research.brief.universe.value
    if universe is None or not universe.symbols:
        return research
    pinned = data_source_id_for_symbols(universe.symbols, universe.market)
    if research.data_source_id == pinned:
        return research
    return replace(research, data_source_id=pinned)


def pool_resolvable_brief(brief: ResearchBrief) -> bool:
    universe = brief.universe.value
    if universe is None:
        return False
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
