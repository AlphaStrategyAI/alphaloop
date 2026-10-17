from __future__ import annotations

from typing import Any

from engine.research.models import Research
from engine.research.planned_data_window import DEFAULT_DATA_SOURCE_ID, planned_data_window
from engine.research.pool_data_shrink import pool_shrink_disclosure, symbols_with_daily_data
from engine.research.user_errors import UserFacingError
from engine.research.symbol_pool import pool_for_market


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
    universe = research.brief.universe.value
    if universe is None:
        return None
    start, end = planned_data_window()
    if research.data_window_start is not None:
        start = research.data_window_start
    if research.data_window_end is not None:
        end = research.data_window_end
    pool = pool_for_market(
        universe.market,
        universe.asset_class,
        universe.underlying_asset_class,
    )
    user_override = universe.user_symbols_override and bool(universe.symbols)
    if user_override:
        symbols = universe.symbols
        list_name = "用户指定标的"
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

    floor = research.brief.coverage_floor.value
    min_assets = floor.min_assets if floor is not None else 0
    dropped = 0
    shrink_note: str | None = None
    if symbols:
        kept = symbols_with_daily_data(symbols, start, end)
        dropped = len(symbols) - len(kept)
        remaining = len(kept)
        if min_assets and remaining < min_assets:
            shrink_note = UserFacingError(
                "POOL_DATA_SHRINK_TOO_FEW",
                (
                    f"部分标的缺少可用行情数据：已从池内剔除 {dropped} 只，"
                    f"剩余 {remaining} 只，低于您认下的至少 {min_assets} 只。"
                    "请放宽最低覆盖或更换标的后再确认开跑。"
                ),
            ).message
        else:
            shrink_note = pool_shrink_disclosure(dropped, remaining)
        symbols = kept

    return {
        "count": len(symbols),
        "listName": list_name,
        "listVersion": list_version,
        "generatedDate": generated,
        "symbols": list(symbols),
        "source": source,
        "overrideNote": "已覆盖默认标的池" if user_override else None,
        "dataStart": start.isoformat(),
        "dataEnd": end.isoformat(),
        "dataCutoff": end.isoformat(),
        "dataSource": research.data_source_id or DEFAULT_DATA_SOURCE_ID,
        "droppedForMissingData": dropped,
        "shrinkNote": shrink_note,
    }
