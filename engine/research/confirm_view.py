from __future__ import annotations

from typing import Any

from engine.research.a1_copy import USER_OVERRIDE_NOTE, USER_SPECIFIED_LIST_NAME
from engine.research.display_names import data_source_label_for_symbols
from engine.research.models import Research
from engine.research.planned_data_window import planned_data_window
from engine.research.pool_data_shrink import pool_shrink_disclosure
from engine.research.symbol_pool import pool_by_version, pool_for_market
from engine.research.symbol_selection_display import symbol_selection_summary_fields
from engine.research.universe_pool import materialize_default_pool


def _resolved_symbols(research: Research) -> tuple[str, ...] | None:
    universe = research.brief.universe.value
    if universe is None:
        return None
    pool = pool_for_market(
        universe.market,
        universe.asset_class,
        universe.underlying_asset_class,
    )
    if universe.symbols:
        return universe.symbols
    if pool is not None:
        return pool.symbols
    return None


def symbol_selection_payload(research: Research) -> dict[str, Any] | None:
    research = materialize_default_pool(research)
    universe = research.brief.universe.value
    if universe is None:
        return None
    start, end = planned_data_window()
    if research.data_window_start is not None:
        start = research.data_window_start
    if research.data_window_end is not None:
        end = research.data_window_end
    pinned_version = universe.symbol_list_version or research.symbol_list_version
    pool = pool_by_version(pinned_version) if pinned_version else None
    if pool is None:
        pool = pool_for_market(
            universe.market,
            universe.asset_class,
            universe.underlying_asset_class,
        )
    user_override = universe.user_symbols_override and bool(universe.symbols)
    if user_override:
        symbols = universe.symbols
        list_name = USER_SPECIFIED_LIST_NAME
        list_version = universe.symbol_list_version or "user"
        generated = ""
        source = "user_override"
    elif universe.symbols:
        symbols = universe.symbols
        list_name = pool.display_name if pool else "已选标的"
        list_version = universe.symbol_list_version or (pool.version_id if pool else "")
        generated = pool.generated_date if pool else ""
        source = "default_pool" if not universe.user_symbols_override else "user_override"
    elif pool is not None:
        symbols = pool.symbols
        list_name = pool.display_name
        list_version = pool.version_id
        generated = pool.generated_date
        source = "default_pool"
    else:
        return None

    dropped = research.pool_data_dropped_count
    shrink_note = pool_shrink_disclosure(dropped, len(symbols))

    payload = symbol_selection_summary_fields(
        count=len(symbols),
        list_name=list_name,
        version_id=list_version,
        generated_date=generated,
        source=source,
        override_note=USER_OVERRIDE_NOTE if user_override else None,
        user_override=user_override,
    )
    payload.update(
        {
            "symbols": list(symbols),
            "dataStart": start.isoformat(),
            "dataEnd": end.isoformat(),
            "dataCutoff": end.isoformat(),
            "dataSource": data_source_label_for_symbols(tuple(symbols), universe.market),
            "droppedForMissingData": dropped,
            "shrinkNote": shrink_note or None,
        }
    )
    return payload
