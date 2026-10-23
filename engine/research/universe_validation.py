from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from engine.research.data_availability import MARKET_DATA_FAILURE_CODES
from engine.research.models import Research, Slot, Universe
from engine.research.planned_data_window import (
    AKSHARE_SINA_DATA_SOURCE_ID,
    data_source_id_for_symbol,
    data_source_id_for_symbols,
    planned_data_window,
)
from engine.research.pool_data_shrink import missing_named_symbols, shrink_pool_to_available_data
from engine.research.symbol_identity import is_cn_etf_symbol, parse_symbol_field, us_listings
from engine.research.symbol_mentions import universe_with_mentions
from engine.research.symbol_pool import EMPTY_POOL_DIALOGUE_PROMPT, pool_for_market
from engine.research.universe_pool import materialize_default_pool
from engine.research.user_errors import UserFacingError

_UNRESOLVED = "无法确认「{token}」属于哪个交易所。请选择交易所，或输入带后缀的完整代码。"
_NO_DATA = "所选数据源没有 {symbol} 的行情，无法开跑。请改代码或换数据源。"
_ETF_UNSUPPORTED = "所选数据源暂不支持 A 股 ETF 行情（{symbol}），无法开跑。"
_ASK_PENDING = "先确认上面的代码再开跑。"
_MIXED = "一次研究只能用同一个市场的标的，这里既有 A 股（{cn_symbols}），也有美股（{us_symbols}）。请删掉其中一边。"


def _named_symbol_label(symbols: tuple[str, ...]) -> str:
    return "、".join(symbols)


def akshare_etf_symbols(symbols: tuple[str, ...]) -> tuple[str, ...]:
    """ETF listings whose selected source is AkShare, which has no ETF prices."""
    return tuple(
        symbol
        for symbol in symbols
        if is_cn_etf_symbol(symbol)
        and data_source_id_for_symbol(symbol) == AKSHARE_SINA_DATA_SOURCE_ID
    )


def _both_markets(symbols: tuple[str, ...]) -> bool:
    cn, us = market_symbol_sides(symbols)
    return bool(cn and us)


def market_symbol_sides(symbols: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """China A-share codes and US tickers named together."""
    cn: list[str] = []
    us: list[str] = []
    for symbol in symbols:
        upper = symbol.upper()
        if upper.endswith((".SH", ".SZ", ".BJ")):
            cn.append(symbol)
        elif "." not in upper and upper.replace("-", "")[:1].isalpha():
            us.append(symbol)
    return tuple(cn), tuple(us)


def reject_unresolved_symbols(research: Research) -> None:
    universe = research.brief.universe.value
    if universe is None:
        return
    if universe.symbol_asks and not universe.unresolved_tokens:
        return
    if not universe.unresolved_tokens and not (universe.user_symbols_override and not universe.symbols):
        return
    token = _named_symbol_label(universe.unresolved_tokens)
    raise UserFacingError(
        "SYMBOL_UNRESOLVED",
        _UNRESOLVED.format(token=token),
        params={"token": token},
    )


def reject_pending_symbol_asks(research: Research) -> None:
    universe = research.brief.universe.value
    if universe is None or not universe.symbol_asks:
        return
    raise UserFacingError("SYMBOL_ASK_PENDING", _ASK_PENDING)


def reject_mixed_markets(research: Research) -> None:
    universe = research.brief.universe.value
    if universe is None:
        return
    cn, us = market_symbol_sides(universe.symbols)
    if not cn or not us:
        return
    cn_symbols = _named_symbol_label(cn)
    us_symbols = _named_symbol_label(us)
    raise UserFacingError(
        "SYMBOL_MIXED_MARKETS",
        _MIXED.format(cn_symbols=cn_symbols, us_symbols=us_symbols),
        params={"cn_symbols": cn_symbols, "us_symbols": us_symbols},
    )


def refresh_symbol_probe(research: Research) -> Research:
    """Record whether a named symbol has bars, once per symbol list."""
    universe = research.brief.universe.value
    if (
        universe is None
        or universe.unresolved_tokens
        or universe.symbol_asks
        or not universe.user_symbols_override
        or not universe.symbols
        or akshare_etf_symbols(universe.symbols)
        or _both_markets(universe.symbols)
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


def _require_draft(research: Research) -> None:
    from engine.research.models import ResearchStatus

    if research.status is not ResearchStatus.DRAFT:
        raise UserFacingError("SYMBOL_EDIT_NOT_DRAFT", "只有草稿上的确认卡可以改标的。")


def _dismissed_with(research: Research, extra: tuple[str, ...]) -> tuple[str, ...]:
    dismissed = list(research.dismissed_symbol_tokens)
    for token in extra:
        if token and token not in dismissed:
            dismissed.append(token)
    return tuple(dismissed)


def _cleared_probe(research: Research, **changes: object) -> Research:
    return replace(
        research,
        symbol_probe_symbols=(),
        symbol_probe_missing=(),
        symbol_probe_unavailable=False,
        **changes,
    )


def apply_symbol_edit(research: Research, symbol: str, now: datetime) -> Research:
    """Replace the confirm-card symbol. An empty field returns to the default pool."""
    _require_draft(research)
    universe = research.brief.universe.value
    if universe is None:
        raise UserFacingError("UNIVERSE_MISSING", EMPTY_POOL_DIALOGUE_PROMPT)
    dismissed = _dismissed_with(
        research,
        tuple(raw for raw, _canonical in universe.inferred_symbols),
    )
    text = symbol.strip()
    if not text:
        cleared = replace(
            universe,
            symbols=(),
            symbol_list_version=None,
            user_symbols_override=False,
            unresolved_tokens=(),
            inferred_symbols=(),
            symbol_asks=(),
            ticker_hints=(),
            recognition_hidden=True,
        )
        brief = replace(research.brief, universe=Slot(cleared, research.brief.universe.locked))
        return _cleared_probe(
            research,
            brief=brief,
            dismissed_symbol_tokens=dismissed,
            updated_at=now,
        )
    mentions = parse_symbol_field(text)
    if not mentions:
        raise UserFacingError(
            "SYMBOL_UNRESOLVED",
            _UNRESOLVED.format(token=text),
            params={"token": text},
        )
    updated = replace(
        universe_with_mentions(universe, mentions),
        recognition_hidden=True,
        ticker_hints=(),
    )
    brief = replace(research.brief, universe=Slot(updated, research.brief.universe.locked))
    return _cleared_probe(
        research,
        brief=brief,
        dismissed_symbol_tokens=dismissed,
        updated_at=now,
    )


def answer_symbol_ask(research: Research, token: str, accept: bool, now: datetime) -> Research:
    """Record one ambiguous-ticker answer. The run stays blocked until none remain."""
    _require_draft(research)
    universe = research.brief.universe.value
    if universe is None:
        raise UserFacingError("UNIVERSE_MISSING", EMPTY_POOL_DIALOGUE_PROMPT)
    match = next((ask for ask in universe.symbol_asks if ask[0] == token), None)
    if match is None:
        return research
    remaining = tuple(ask for ask in universe.symbol_asks if ask[0] != token)
    symbols = list(universe.symbols)
    dismissed = research.dismissed_symbol_tokens
    if accept:
        if match[1] not in symbols:
            symbols.append(match[1])
    else:
        dismissed = _dismissed_with(research, (token,))
    claimed = bool(symbols or remaining or universe.unresolved_tokens)
    updated = replace(
        universe,
        symbols=tuple(symbols),
        symbol_list_version=None if claimed else universe.symbol_list_version,
        user_symbols_override=claimed,
        symbol_asks=remaining,
    )
    brief = replace(research.brief, universe=Slot(updated, research.brief.universe.locked))
    return _cleared_probe(
        research,
        brief=brief,
        dismissed_symbol_tokens=dismissed,
        updated_at=now,
    )


def use_hinted_symbol(research: Research, symbol: str, now: datetime) -> Research:
    """One click on a default-pool hint. The symbol is chosen, not auto-recognized."""
    _require_draft(research)
    universe = research.brief.universe.value
    if universe is None:
        raise UserFacingError("UNIVERSE_MISSING", EMPTY_POOL_DIALOGUE_PROMPT)
    canonical = symbol.strip().upper().replace(".", "-")
    if canonical not in us_listings() and not any(hint[1] == canonical for hint in universe.ticker_hints):
        raise UserFacingError(
            "SYMBOL_UNRESOLVED",
            _UNRESOLVED.format(token=symbol.strip()),
            params={"token": symbol.strip()},
        )
    updated = replace(
        universe,
        symbols=(canonical,),
        symbol_list_version=None,
        user_symbols_override=True,
        unresolved_tokens=(),
        inferred_symbols=(),
        symbol_asks=(),
        ticker_hints=(),
        recognition_hidden=True,
    )
    brief = replace(research.brief, universe=Slot(updated, research.brief.universe.locked))
    dismissed = _dismissed_with(research, tuple(raw for raw, _canonical in universe.ticker_hints))
    return _cleared_probe(
        research,
        brief=brief,
        dismissed_symbol_tokens=dismissed,
        updated_at=now,
    )


def resolve_universe_symbols(research: Research, now: datetime) -> Research:
    """Apply versioned default pool or validate user symbols before confirm."""
    research = materialize_default_pool(research)
    universe = research.brief.universe.value
    if universe is None:
        raise UserFacingError("UNIVERSE_MISSING", EMPTY_POOL_DIALOGUE_PROMPT)
    reject_unresolved_symbols(research)
    reject_pending_symbol_asks(research)
    reject_mixed_markets(research)
    universe = research.brief.universe.value
    assert universe is not None
    etfs = akshare_etf_symbols(universe.symbols)
    if etfs:
        symbol = _named_symbol_label(etfs)
        raise UserFacingError(
            "SYMBOL_ETF_UNSUPPORTED",
            _ETF_UNSUPPORTED.format(symbol=symbol),
            params={"symbol": symbol},
        )
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
