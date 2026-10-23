from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from engine.research.data_availability import MARKET_DATA_FAILURE_CODES
from engine.research.models import Research, Slot, Universe
from engine.research.planned_data_window import (
    data_source_id_for_symbols,
    planned_data_window,
)
from engine.research.pool_data_shrink import missing_named_symbols, shrink_pool_to_available_data
from engine.research.symbol_identity import parse_symbol_field
from engine.research.symbol_mentions import universe_with_mentions
from engine.research.symbol_pool import EMPTY_POOL_DIALOGUE_PROMPT, pool_for_market
from engine.research.universe_pool import materialize_default_pool
from engine.research.user_errors import UserFacingError

_UNRESOLVED = "无法确认「{token}」的交易所。请选择或输入完整代码。"
_NO_DATA = "所选数据源没有 {symbol} 的行情，无法开跑。"


def _named_symbol_label(symbols: tuple[str, ...]) -> str:
    return "、".join(symbols)


def reject_unresolved_symbols(research: Research) -> None:
    universe = research.brief.universe.value
    if universe is None:
        return
    if not universe.unresolved_tokens and not (universe.user_symbols_override and not universe.symbols):
        return
    token = _named_symbol_label(universe.unresolved_tokens)
    raise UserFacingError(
        "SYMBOL_UNRESOLVED",
        _UNRESOLVED.format(token=token),
        params={"token": token},
    )


def refresh_symbol_probe(research: Research) -> Research:
    """Record whether a named symbol has bars, once per symbol list."""
    universe = research.brief.universe.value
    if (
        universe is None
        or universe.unresolved_tokens
        or not universe.user_symbols_override
        or not universe.symbols
    ):
        return research
    if research.symbol_probe_symbols == universe.symbols:
        return research
    start, end = planned_data_window()
    try:
        missing = missing_named_symbols(universe.symbols, start, end)
    except UserFacingError as error:
        if error.code in MARKET_DATA_FAILURE_CODES:
            return replace(
                research,
                symbol_probe_symbols=universe.symbols,
                symbol_probe_missing=(),
                symbol_probe_unavailable=True,
            )
        raise
    return replace(
        research,
        symbol_probe_symbols=universe.symbols,
        symbol_probe_missing=missing,
        symbol_probe_unavailable=False,
    )


def apply_symbol_edit(research: Research, symbol: str, now: datetime) -> Research:
    """Replace the confirm-card symbol. An uncertain code stays unresolved."""
    from engine.research.models import ResearchStatus

    if research.status is not ResearchStatus.DRAFT:
        raise UserFacingError("SYMBOL_EDIT_NOT_DRAFT", "只有草稿上的确认卡可以改标的。")
    universe = research.brief.universe.value
    if universe is None:
        raise UserFacingError("UNIVERSE_MISSING", EMPTY_POOL_DIALOGUE_PROMPT)
    mentions = parse_symbol_field(symbol)
    if not mentions:
        raise UserFacingError(
            "SYMBOL_UNRESOLVED",
            _UNRESOLVED.format(token=symbol.strip()),
            params={"token": symbol.strip()},
        )
    updated = universe_with_mentions(universe, mentions)
    brief = replace(research.brief, universe=Slot(updated, research.brief.universe.locked))
    return replace(
        research,
        brief=brief,
        symbol_probe_symbols=(),
        symbol_probe_missing=(),
        symbol_probe_unavailable=False,
        updated_at=now,
    )


def resolve_universe_symbols(research: Research, now: datetime) -> Research:
    """Apply versioned default pool or validate user symbols before confirm."""
    research = materialize_default_pool(research)
    universe = research.brief.universe.value
    if universe is None:
        raise UserFacingError("UNIVERSE_MISSING", EMPTY_POOL_DIALOGUE_PROMPT)
    reject_unresolved_symbols(research)
    universe = research.brief.universe.value
    assert universe is not None
    floor = research.brief.coverage_floor.value
    min_assets = floor.min_assets if floor is not None else 0

    if universe.symbols and universe.user_symbols_override:
        if min_assets and len(universe.symbols) < min_assets:
            raise UserFacingError(
                "UNIVERSE_TOO_FEW_SYMBOLS",
                f"当前仅 {len(universe.symbols)} 个标的，低于最低覆盖要求的 {min_assets} 个。",
            )
        start, end = planned_data_window(now)
        missing = missing_named_symbols(universe.symbols, start, end)
        kept = tuple(symbol for symbol in universe.symbols if symbol not in set(missing))
        if missing and not kept:
            symbol = _named_symbol_label(missing)
            raise UserFacingError(
                "SYMBOL_NO_DATA",
                _NO_DATA.format(symbol=symbol),
                params={"symbol": symbol},
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
    pinned = research.brief.universe.value or universe
    return replace(
        research,
        brief=locked_brief,
        symbol_list_version=version,
        data_window_start=start,
        data_window_end=end,
        data_source_id=data_source_id_for_symbols(pinned.symbols, pinned.market),
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
