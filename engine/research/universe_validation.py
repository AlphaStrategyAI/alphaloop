from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from engine.research.data_availability import MARKET_DATA_FAILURE_CODES
from engine.research.models import Research, Slot, Universe
from engine.research.planned_data_window import (
    AKSHARE_SINA_DATA_SOURCE_ID,
    data_source_id_for_symbol,
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
_AMOUNT = "「{token}」看起来像金额，也可能是代码 {symbol}。要把它当作标的吗？"
_MIXED = "一次研究只能用同一个市场的标的，这里既有 A 股（{cn_symbols}），也有美股（{us_symbols}）。请删掉其中一边。"
_MISMATCH = "描述里的市场是{market}，但 {symbols} 不属于这个市场。请删掉这些代码，或改成对应的市场。"
_SOURCE_MISMATCH = "所选数据源 {source} 不提供{market}行情，和这些标的对不上，无法开跑。请换一个{market}数据源。"
_MARKET_CHOICE = "描述里没有写市场。这次研究用哪个市场的默认池？"
_SOURCE_EN = {
    "yahoo_daily": "Yahoo daily",
    "akshare_sina_daily": "AkShare daily (Sina first)",
}


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
    if all(len(ask) > 2 and ask[2] == "amount" for ask in universe.symbol_asks):
        token, symbol, _kind = universe.symbol_asks[0]
        raise UserFacingError(
            "SYMBOL_AMOUNT_LIKE",
            _AMOUNT.format(token=token, symbol=symbol),
            params={"token": token, "symbol": symbol},
        )
    raise UserFacingError("SYMBOL_ASK_PENDING", _ASK_PENDING)


def _market_label(market: object) -> tuple[str, str]:
    from engine.research.models import Market

    if market is Market.US:
        return "美股", "US stocks"
    return "A 股", "China A-shares"


def reject_market_mismatches(research: Research) -> None:
    """Stated market and the named symbols have to be the same market."""
    universe = research.brief.universe.value
    if universe is None:
        return
    symbols: list[str] = []
    if universe.market_mismatches:
        symbols = [canonical for _raw, canonical in universe.market_mismatches]
    else:
        cn, us = market_symbol_sides(universe.symbols)
        from engine.research.models import Market

        if universe.market is Market.CN and us and not cn:
            symbols = list(us)
        elif universe.market is Market.US and cn and not us:
            symbols = list(cn)
    if not symbols:
        return
    market, market_en = _market_label(universe.market)
    joined = _named_symbol_label(tuple(symbols))
    raise UserFacingError(
        "SYMBOL_MARKET_MISMATCH",
        _MISMATCH.format(market=market, symbols=joined),
        params={
            "market": market,
            "marketEn": market_en,
            "symbols": joined,
            "n": len(symbols),
        },
    )


def reject_source_market_mismatch(research: Research, source_id: str, settings_path: object) -> None:
    """A chosen price source has to belong to the universe market.

    Yahoo is US. AkShare is China A-shares. A licensed file configured for the
    other market is the same disagreement. An empty source is not this error.
    """
    from pathlib import Path

    from engine.research.models import Market
    from engine.research.planned_data_window import (
        AKSHARE_SINA_DATA_SOURCE_ID,
        DEFAULT_DATA_SOURCE_ID,
    )
    from engine.research.price_source_choice import configured_licensed_sources

    universe = research.brief.universe.value
    source = source_id.strip()
    if universe is None or not source:
        return
    disagrees = (
        source == DEFAULT_DATA_SOURCE_ID and universe.market is not Market.US
    ) or (
        source == AKSHARE_SINA_DATA_SOURCE_ID and universe.market is not Market.CN
    )
    if source not in {DEFAULT_DATA_SOURCE_ID, AKSHARE_SINA_DATA_SOURCE_ID}:
        path = settings_path if isinstance(settings_path, Path) else Path(str(settings_path))
        other = Market.US if universe.market is Market.CN else Market.CN
        other_ids = {item.source_id for item in configured_licensed_sources(path, other)}
        same_ids = {item.source_id for item in configured_licensed_sources(path, universe.market)}
        disagrees = source in other_ids and source not in same_ids
    if not disagrees:
        return
    from engine.research.display_names import data_source_label

    market, market_en = _market_label(universe.market)
    source_zh = data_source_label(source)
    raise UserFacingError(
        "SYMBOL_SOURCE_MISMATCH",
        _SOURCE_MISMATCH.format(source=source_zh, market=market),
        params={
            "source": source_zh,
            "market": market,
            "sourceEn": _SOURCE_EN.get(source, source_zh),
            "marketEn": market_en,
        },
    )


def reject_unspecified_market(research: Research) -> None:
    """A description with no market waits for an explicit pool choice."""
    universe = research.brief.universe.value
    if universe is None or not universe.market_unspecified:
        return
    raise UserFacingError("MARKET_CHOICE_PENDING", _MARKET_CHOICE)


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
        or universe.market_mismatches
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
        market_switch_market="",
        market_switch_benchmark="",
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
            symbol_ask_answers=(),
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


def _ask_kind(ask: tuple[str, ...]) -> str:
    return ask[2] if len(ask) > 2 else "ask"


def answer_symbol_ask(research: Research, token: str, accept: bool, now: datetime) -> Research:
    """Record one ambiguous-ticker answer. The run stays blocked until none remain."""
    _require_draft(research)
    universe = research.brief.universe.value
    if universe is None:
        raise UserFacingError("UNIVERSE_MISSING", EMPTY_POOL_DIALOGUE_PROMPT)
    match = next((ask for ask in universe.symbol_asks if ask[0] == token), None)
    if match is None:
        return research
    kind = _ask_kind(match)
    remaining = tuple(ask for ask in universe.symbol_asks if ask[0] != token)
    symbols = list(universe.symbols)
    dismissed = research.dismissed_symbol_tokens
    if accept:
        if match[1] not in symbols:
            symbols.append(match[1])
    else:
        dismissed = _dismissed_with(research, (token,))
    answers = tuple(answer for answer in universe.symbol_ask_answers if answer[0] != token)
    answers = (*answers, (token, match[1], kind, accept))
    claimed = bool(symbols or remaining or universe.unresolved_tokens)
    updated = replace(
        universe,
        symbols=tuple(symbols),
        symbol_list_version=None if claimed else universe.symbol_list_version,
        user_symbols_override=claimed,
        symbol_asks=remaining,
        symbol_ask_answers=answers,
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
        symbol_ask_answers=(),
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


def revert_symbol_ask(research: Research, token: str, now: datetime) -> Research:
    """Put an answered row back into the ask state and block Run again."""
    _require_draft(research)
    universe = research.brief.universe.value
    if universe is None:
        raise UserFacingError("UNIVERSE_MISSING", EMPTY_POOL_DIALOGUE_PROMPT)
    match = next((answer for answer in universe.symbol_ask_answers if answer[0] == token), None)
    if match is None:
        return research
    raw, symbol, kind, accept = match
    answers = tuple(answer for answer in universe.symbol_ask_answers if answer[0] != token)
    asks = tuple(ask for ask in universe.symbol_asks if ask[0] != token)
    asks = (*asks, (raw, symbol, kind))
    symbols = [] if not universe.user_symbols_override else list(universe.symbols)
    if accept and symbol in symbols:
        symbols.remove(symbol)
    dismissed = tuple(item for item in research.dismissed_symbol_tokens if item != raw)
    updated = replace(
        universe,
        symbols=tuple(symbols),
        symbol_list_version=None,
        user_symbols_override=True,
        symbol_asks=asks,
        symbol_ask_answers=answers,
    )
    brief = replace(research.brief, universe=Slot(updated, research.brief.universe.locked))
    return _cleared_probe(
        research,
        brief=brief,
        dismissed_symbol_tokens=dismissed,
        updated_at=now,
    )


def remove_market_side(research: Research, side: str, now: datetime) -> Research:
    """Drop one market and retarget the market and benchmark to what remains.

    The data source is cleared, not switched. Preselection runs again for the
    new market and does not choose Yahoo or AkShare.
    """
    from engine.metrics import benchmark_for
    from engine.research.models import Market

    _require_draft(research)
    universe = research.brief.universe.value
    if universe is None:
        raise UserFacingError("UNIVERSE_MISSING", EMPTY_POOL_DIALOGUE_PROMPT)
    if side not in {"cn", "us"}:
        raise UserFacingError("SYMBOL_MARKET_MISMATCH", _MISMATCH.format(market="", symbols=side))
    cn, us = market_symbol_sides(universe.symbols)
    drop = set(cn if side == "cn" else us)
    keep = tuple(symbol for symbol in universe.symbols if symbol not in drop)
    inferred = tuple(
        pair for pair in universe.inferred_symbols if pair[1] not in drop
    )
    dismissed = _dismissed_with(
        research,
        tuple(raw for raw, symbol in universe.inferred_symbols if symbol in drop),
    )
    previous = universe.market
    market = Market.US if side == "cn" else Market.CN
    updated = replace(
        universe,
        market=market,
        symbols=keep,
        symbol_list_version=None,
        user_symbols_override=bool(keep or universe.unresolved_tokens or universe.symbol_asks),
        inferred_symbols=inferred,
        recognition_hidden=False,
    )
    benchmark = benchmark_for(updated).name
    brief = replace(research.brief, universe=Slot(updated, research.brief.universe.locked))
    cleared = _cleared_probe(
        research,
        brief=brief,
        dismissed_symbol_tokens=dismissed,
        data_source_id="",
        updated_at=now,
    )
    if previous == market:
        return cleared
    return replace(
        cleared,
        market_switch_market=market.value,
        market_switch_benchmark=benchmark,
    )


def dismiss_mismatched_symbol(research: Research, symbol: str, now: datetime) -> Research:
    """Drop one stated-market mismatch so the description does not put it back."""
    from engine.research.symbol_mentions import described_mentions

    _require_draft(research)
    universe = research.brief.universe.value
    if universe is None:
        raise UserFacingError("UNIVERSE_MISSING", EMPTY_POOL_DIALOGUE_PROMPT)
    match = next(
        (
            pair
            for pair in universe.market_mismatches
            if pair[1] == symbol or pair[0] == symbol
        ),
        None,
    )
    if match is None:
        return research
    raw, canonical = match
    dismissed = _dismissed_with(research, (raw, canonical))
    mentions = described_mentions(replace(research, dismissed_symbol_tokens=dismissed))
    rebuilt = universe_with_mentions(
        replace(
            universe,
            symbols=(),
            symbol_list_version=None,
            user_symbols_override=False,
            unresolved_tokens=(),
            inferred_symbols=(),
            symbol_asks=(),
            ticker_hints=(),
            market_mismatches=(),
            unrecognized_tokens=(),
            recognition_hidden=False,
        ),
        mentions,
    )
    brief = replace(research.brief, universe=Slot(rebuilt, research.brief.universe.locked))
    return _cleared_probe(
        research,
        brief=brief,
        dismissed_symbol_tokens=dismissed,
        updated_at=now,
    )


def choose_default_market(research: Research, market_name: str, now: datetime) -> Research:
    """Pick the market for a description that named none.

    Neither side is remembered. The benchmark follows the market, and the
    data source is cleared so preselection runs again.
    """
    from engine.research.models import Market

    _require_draft(research)
    universe = research.brief.universe.value
    if universe is None:
        raise UserFacingError("UNIVERSE_MISSING", EMPTY_POOL_DIALOGUE_PROMPT)
    if market_name not in {"CN", "US"}:
        raise UserFacingError("MARKET_CHOICE_PENDING", _MARKET_CHOICE)
    if not universe.market_unspecified:
        return research
    market = Market(market_name)
    updated = replace(universe, market=market, market_unspecified=False)
    brief = replace(research.brief, universe=Slot(updated, research.brief.universe.locked))
    return _cleared_probe(
        research,
        brief=brief,
        data_source_id="",
        updated_at=now,
    )


def resolve_universe_symbols(research: Research, now: datetime) -> Research:
    """Apply versioned default pool or validate user symbols before confirm."""
    research = materialize_default_pool(research)
    universe = research.brief.universe.value
    if universe is None:
        raise UserFacingError("UNIVERSE_MISSING", EMPTY_POOL_DIALOGUE_PROMPT)
    reject_unspecified_market(research)
    reject_market_mismatches(research)
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
