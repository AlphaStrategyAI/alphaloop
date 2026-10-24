from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from engine.research.models import Research, Slot, Universe
from engine.research.planned_data_window import planned_data_window
from engine.research.pool_data_shrink import shrink_pool_to_available_data
from engine.research.universe_pool import materialize_default_pool
from engine.research.symbol_pool import EMPTY_POOL_DIALOGUE_PROMPT, pool_for_market
from engine.research.user_errors import UserFacingError


def resolve_universe_symbols(research: Research, now: datetime) -> Research:
    """Apply versioned default pool or validate user symbols before confirm."""
    research = materialize_default_pool(research)
    universe = research.brief.universe.value
    if universe is None:
        raise UserFacingError("UNIVERSE_MISSING", EMPTY_POOL_DIALOGUE_PROMPT)
    floor = research.brief.coverage_floor.value
    min_assets = floor.min_assets if floor is not None else 0

    if universe.symbols and universe.user_symbols_override:
        if min_assets and len(universe.symbols) < min_assets:
            raise UserFacingError(
                "UNIVERSE_TOO_FEW_SYMBOLS",
                f"当前仅 {len(universe.symbols)} 个标的，低于最低覆盖要求的 {min_assets} 个。",
            )
        return _pin_window(research, universe, now)

    if universe.symbols and not universe.user_symbols_override:
        return _pin_window(research, universe, now)

    pool = pool_for_market(
        universe.market,
        universe.asset_class,
        universe.underlying_asset_class,
    )
    if pool is None or not pool.symbols:
        raise UserFacingError("UNIVERSE_SYMBOLS_EMPTY", EMPTY_POOL_DIALOGUE_PROMPT)
    if min_assets and len(pool.symbols) < min_assets:
        raise UserFacingError(
            "UNIVERSE_DEFAULT_TOO_SMALL",
            f"默认标的池仅 {len(pool.symbols)} 只，无法满足至少 {min_assets} 只的要求，请调低底线或指定更多标的。",
        )
    updated_universe = Universe(
        universe.market,
        universe.asset_class,
        universe.underlying_asset_class,
        pool.symbols,
        symbol_list_version=pool.version_id,
        user_symbols_override=False,
    )
    brief = replace(research.brief, universe=Slot(updated_universe, True))
    return _pin_window(
        replace(research, brief=brief),
        updated_universe,
        now,
        pool_version=pool.version_id,
    )


def ensure_runnable_universe(research: Research) -> Research:
    """Confirm-time entry: resolve symbols and pin data window."""
    return resolve_universe_symbols(research, datetime.now(UTC))


def _pin_window(
    research: Research,
    universe: Universe,
    now: datetime,
    *,
    pool_version: str | None = None,
) -> Research:
    start, end = planned_data_window(now)
    version = pool_version or universe.symbol_list_version
    research = _shrink_universe_symbols(research, start, end)
    locked_brief = research.brief
    for name in ("thesis", "universe", "max_effective_hours", "round1_methods", "coverage_floor"):
        slot = getattr(locked_brief, name)
        if slot.value is not None:
            locked_brief = replace(locked_brief, **{name: Slot(slot.value, True)})
    return replace(
        research,
        brief=locked_brief,
        symbol_list_version=version,
        data_window_start=start,
        data_window_end=end,
        updated_at=now,
    )


def _shrink_universe_symbols(
    research: Research,
    start: date,
    end: date,
) -> Research:
    universe = research.brief.universe.value
    if universe is None or not universe.symbols:
        return research
    floor = research.brief.coverage_floor.value
    min_assets = floor.min_assets if floor is not None else 0
    result = shrink_pool_to_available_data(
        universe.symbols,
        start,
        end,
        min_assets=min_assets,
    )
    dropped = result.dropped_count
    if result.symbols != universe.symbols:
        updated_universe = Universe(
            universe.market,
            universe.asset_class,
            universe.underlying_asset_class,
            result.symbols,
            symbol_list_version=universe.symbol_list_version,
            user_symbols_override=universe.user_symbols_override,
        )
        brief = replace(research.brief, universe=Slot(updated_universe, True))
        research = replace(research, brief=brief)
    return replace(research, pool_data_dropped_count=dropped)
