from __future__ import annotations

from typing import Any

from engine.research.a1_copy import USER_OVERRIDE_NOTE, USER_SPECIFIED_LIST_NAME
from engine.research.data_availability import MARKET_DATA_FAILURE_CODES
from engine.research.display_names import data_source_label
from engine.research.models import Research, ResearchStatus
from engine.research.planned_data_window import data_source_id_for_symbols, planned_data_window
from engine.research.pool_data_shrink import pool_shrink_disclosure
from engine.research.symbol_pool import pool_for_market, pool_for_universe
from engine.research.symbol_selection_display import symbol_selection_summary_fields
from engine.research.universe_pool import materialize_default_pool
from engine.research.universe_validation import akshare_etf_symbols, market_symbol_sides


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
    """The source the user already chose. Symbols do not fill this in."""
    del symbols, market
    if research.status is not ResearchStatus.DRAFT:
        return research.data_source_id
    return research.data_source_id


def symbol_resolution_payload(research: Research) -> dict[str, Any] | None:
    """Inference, asks, hints, and block state for the confirm card."""
    universe = research.brief.universe.value
    if universe is None:
        return None
    cn, us = market_symbol_sides(tuple(universe.symbols))
    mixed = bool(cn and us)
    asks = tuple(universe.symbol_asks)
    mismatches = tuple(universe.market_mismatches)
    unrecognized = tuple(universe.unrecognized_tokens)
    default_pool = (
        not universe.user_symbols_override
        and not asks
        and not universe.unresolved_tokens
        and not mismatches
    )
    hints = tuple(universe.ticker_hints)[:3] if default_pool else ()
    named = bool(
        universe.user_symbols_override
        or universe.unresolved_tokens
        or universe.inferred_symbols
        or asks
        or universe.symbol_ask_answers
        or hints
        or mixed
        or mismatches
        or unrecognized
    )
    if universe.market_unspecified:
        named = True
    if not named:
        return None
    code: str | None = None
    blocked = False
    token = "、".join(universe.unresolved_tokens) if universe.unresolved_tokens else None
    symbol = universe.symbols[0] if universe.user_symbols_override and universe.symbols else None
    etfs = akshare_etf_symbols(tuple(universe.symbols))
    if universe.market_unspecified:
        blocked = True
        code = "MARKET_CHOICE_PENDING"
        symbol = None
    elif mismatches:
        blocked = True
        code = "SYMBOL_MARKET_MISMATCH"
        symbol = None
    elif universe.unresolved_tokens or (
        universe.user_symbols_override and not universe.symbols and not asks
    ):
        blocked = True
        code = "SYMBOL_UNRESOLVED"
    elif asks:
        blocked = True
        code = (
            "SYMBOL_AMOUNT_LIKE"
            if all(len(ask) > 2 and ask[2] == "amount" for ask in asks)
            else "SYMBOL_ASK_PENDING"
        )
    elif mixed:
        blocked = True
        code = "SYMBOL_MIXED_MARKETS"
        symbol = None
    elif etfs:
        blocked = True
        code = "SYMBOL_ETF_UNSUPPORTED"
        symbol = "、".join(etfs)
    elif (
        universe.user_symbols_override
        and research.symbol_probe_symbols == universe.symbols
        and research.symbol_probe_missing
        and set(research.symbol_probe_missing) >= set(universe.symbols)
    ):
        blocked = True
        code = "SYMBOL_NO_DATA"
        symbol = "、".join(research.symbol_probe_missing)
    pool_count = None
    if hints or unrecognized:
        pool = pool_for_market(
            universe.market,
            universe.asset_class,
            universe.underlying_asset_class,
        )
        pool_count = len(pool.symbols) if pool is not None else len(universe.symbols)
    visible_symbols = list(universe.symbols) if universe.user_symbols_override else []
    inferred = [] if universe.recognition_hidden else [
        {"raw": raw, "symbol": canonical}
        for raw, canonical in universe.inferred_symbols
    ]
    return {
        "blocked": blocked,
        "code": code,
        "token": token,
        "symbol": symbol,
        "symbols": visible_symbols,
        "inferred": inferred,
        "editable": True,
        "asks": [
            {"token": ask[0], "symbol": ask[1], "kind": ask[2] if len(ask) > 2 else "ask"}
            for ask in asks
        ],
        "answers": [
            {"token": token, "symbol": canonical, "kind": kind, "accept": accept}
            for token, canonical, kind, accept in universe.symbol_ask_answers
        ],
        "hints": [{"token": raw, "symbol": canonical} for raw, canonical in hints],
        "poolCount": pool_count,
        "cnSymbols": "、".join(cn) if mixed else None,
        "usSymbols": "、".join(us) if mixed else None,
        "mismatches": [canonical for _raw, canonical in mismatches],
        "mismatchMarket": universe.market.value if mismatches else None,
        "unrecognized": [{"token": raw} for raw in unrecognized],
    }


def symbol_selection_payload(research: Research) -> dict[str, Any] | None:
    research = materialize_default_pool(research)
    universe = research.brief.universe.value
    if universe is None or universe.market_unspecified:
        return None
    if (universe.user_symbols_override or universe.unresolved_tokens) and not universe.symbols:
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
    selected = _card_data_source_id(research, tuple(symbols), universe.market)
    offered = data_source_id_for_symbols(tuple(symbols), universe.market)
    payload.update(
        {
            "symbols": list(symbols),
            "dataStart": start.isoformat(),
            "dataEnd": end.isoformat(),
            "dataCutoff": end.isoformat(),
            "dataSource": data_source_label(selected),
            "dataSourceId": selected or None,
            "dataSourcePending": not bool(selected),
            "offeredDataSourceId": offered,
            "offeredDataSource": data_source_label(offered),
            "droppedForMissingData": dropped,
            "shrinkNote": shrink_note or None,
        }
    )
    return payload
