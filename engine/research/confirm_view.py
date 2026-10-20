from __future__ import annotations

from typing import Any

from engine.research.a1_copy import USER_OVERRIDE_NOTE, USER_SPECIFIED_LIST_NAME
from engine.research.data_availability import MARKET_DATA_FAILURE_CODES
from engine.research.display_names import data_source_label
from engine.research.models import Research, ResearchStatus
from engine.research.planned_data_window import data_source_id_for_symbols, planned_data_window
from engine.research.pool_data_shrink import pool_shrink_disclosure
from engine.research.symbol_pool import pool_for_universe
from engine.research.symbol_selection_display import symbol_selection_summary_fields
from engine.research.universe_pool import materialize_default_pool


def _resolved_symbols(research: Research) -> tuple[str, ...] | None:
    universe = research.brief.universe.value
    if universe is None:
        return None
    pool = pool_for_universe(
        universe.market,
        universe.asset_class,
        universe.underlying_asset_class,
        universe.symbol_list_version,
    )
    if universe.symbols:
        return universe.symbols
    if pool is not None:
        return pool.symbols
    return None


def confirm_data_notice_text(research: Research) -> str | None:
    """Last assistant line when it is a confirm-time fetch failure."""
    notice = confirm_data_notice(research)
    if notice is None:
        return None
    return str(notice["text"])


def confirm_data_notice(research: Research) -> dict[str, Any] | None:
    """Legacy sentence plus the I0 code and params, when the turn recorded them."""
    if not research.dialogue:
        return None
    last = research.dialogue[-1]
    if last.role.value != "assistant":
        return None
    coded = bool(last.error_code and last.error_code in MARKET_DATA_FAILURE_CODES)
    textual = any(code in last.text for code in MARKET_DATA_FAILURE_CODES)
    if not coded and not textual:
        return None
    payload: dict[str, Any] = {"text": last.text}
    if last.error_code:
        payload["code"] = last.error_code
        payload["params"] = dict(last.error_params or {})
    return payload


def _card_data_source_id(
    research: Research,
    symbols: tuple[str, ...],
    market: object,
) -> str:
    if research.status is not ResearchStatus.DRAFT:
        return research.data_source_id
    if symbols:
        return data_source_id_for_symbols(symbols, market)
    return research.data_source_id


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
    pool = pool_for_universe(
        universe.market,
        universe.asset_class,
        universe.underlying_asset_class,
        universe.symbol_list_version or research.symbol_list_version,
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
            "dataSource": data_source_label(
                _card_data_source_id(research, tuple(symbols), universe.market)
            ),
            "droppedForMissingData": dropped,
            "shrinkNote": shrink_note or None,
        }
    )
    return payload
