"""Drop pool symbols with no daily data before confirm (subset-only, never add)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

import pandas as pd

from engine.research.user_errors import UserFacingError

if TYPE_CHECKING:
    from engine.research.gather import DataPort

_LOADER: DataPort | None = None


class SymbolDataLoader(Protocol):
    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame: ...


def set_pool_data_loader(loader: SymbolDataLoader | None) -> None:
    """Test hook: inject a fake loader; production uses RoutingDataAdapter."""
    global _LOADER
    _LOADER = loader


def _production_loader() -> SymbolDataLoader:
    if _LOADER is not None:
        return _LOADER
    from engine.research.gather import AkShareDataAdapter, RoutingDataAdapter, YahooDataAdapter

    return RoutingDataAdapter(YahooDataAdapter(), AkShareDataAdapter())


@dataclass(frozen=True, slots=True)
class PoolDataShrinkResult:
    symbols: tuple[str, ...]
    dropped: tuple[str, ...]

    @property
    def dropped_count(self) -> int:
        return len(self.dropped)

    @property
    def remaining_count(self) -> int:
        return len(self.symbols)


def symbols_with_daily_data(
    symbols: tuple[str, ...],
    start: date,
    end: date,
    loader: SymbolDataLoader | None = None,
) -> tuple[str, ...]:
    if not symbols:
        return ()
    data = (loader or _production_loader()).load_daily(symbols, start, end)
    available: list[str] = []
    for symbol in symbols:
        if symbol not in data.columns:
            continue
        series = data[symbol]
        if series.notna().sum() > 0:
            available.append(symbol)
    return tuple(available)


def shrink_pool_to_available_data(
    symbols: tuple[str, ...],
    start: date,
    end: date,
    *,
    min_assets: int,
    loader: SymbolDataLoader | None = None,
) -> PoolDataShrinkResult:
    """Keep only symbols that have data; never add symbols outside ``symbols``."""
    if not symbols:
        raise UserFacingError("UNIVERSE_SYMBOLS_EMPTY", "尚未选定任何标的，请先说明资产范围。")
    kept = symbols_with_daily_data(symbols, start, end, loader)
    dropped = tuple(s for s in symbols if s not in kept)
    if min_assets and len(kept) < min_assets:
        raise UserFacingError(
            "POOL_DATA_SHRINK_TOO_FEW",
            (
                f"部分标的缺少可用行情数据：已从池内剔除 {len(dropped)} 只，"
                f"剩余 {len(kept)} 只，低于您认下的至少 {min_assets} 只。"
                "请放宽最低覆盖、指定更多标的，或更换数据窗口后再确认开跑。"
            ),
        )
    return PoolDataShrinkResult(kept, dropped)


def pool_shrink_disclosure(dropped: int, remaining: int) -> str:
    return f"因缺少行情数据，已从标的池剔除 {dropped} 只，剩余 {remaining} 只可用于本轮研究。"
