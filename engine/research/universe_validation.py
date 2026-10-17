from __future__ import annotations

from dataclasses import replace

from engine.research.default_universe import default_universe_symbols
from engine.research.models import Research, Slot, Universe
from engine.research.user_errors import UserFacingError


def ensure_runnable_universe(research: Research) -> Research:
    """Apply default symbols or reject confirm when universe has no tickers."""
    universe = research.brief.universe.value
    if universe is None or not research.brief.universe.locked:
        raise UserFacingError("UNIVERSE_NOT_LOCKED", "请先锁定市场与资产类别。")
    floor = research.brief.coverage_floor.value
    if universe.symbols:
        if floor and len(universe.symbols) < floor.min_assets:
            raise UserFacingError(
                "UNIVERSE_TOO_FEW_SYMBOLS",
                f"当前仅 {len(universe.symbols)} 个标的，低于最低覆盖要求的 {floor.min_assets} 个。",
            )
        return research
    if floor is None or floor.min_assets <= 0:
        return research
    proposed = default_universe_symbols(
        universe.market,
        universe.asset_class,
        universe.underlying_asset_class,
    )
    if not proposed:
        raise UserFacingError(
            "UNIVERSE_SYMBOLS_EMPTY",
            "未指定具体标的，且当前市场暂无默认标的池。请在对话中写明股票或 ETF 代码。",
        )
    if len(proposed) < floor.min_assets:
        raise UserFacingError(
            "UNIVERSE_DEFAULT_TOO_SMALL",
            "默认标的数量不足以满足最低覆盖要求，请手动补充标的。",
        )
    updated_universe = Universe(
        universe.market,
        universe.asset_class,
        universe.underlying_asset_class,
        proposed,
    )
    brief = replace(research.brief, universe=Slot(updated_universe, True))
    return replace(research, brief=brief)
