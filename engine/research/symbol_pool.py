"""Versioned, checked-in symbol pools — never chosen at runtime by a model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from engine.research.models import AssetClass, Market

_POOLS_DIR = Path(__file__).resolve().parent / "symbol_pools"


@dataclass(frozen=True, slots=True)
class SymbolPool:
    version_id: str
    display_name: str
    generated_date: str
    market: Market
    asset_class: AssetClass
    underlying_asset_class: AssetClass
    symbols: tuple[str, ...]


@lru_cache(maxsize=16)
def _load_pool_file(path: Path) -> SymbolPool:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return SymbolPool(
        version_id=str(raw["version_id"]),
        display_name=str(raw["display_name"]),
        generated_date=str(raw["generated_date"]),
        market=Market(raw["market"]),
        asset_class=AssetClass(raw["asset_class"]),
        underlying_asset_class=AssetClass(raw["underlying_asset_class"]),
        symbols=tuple(str(s) for s in raw["symbols"]),
    )


def list_pool_files() -> tuple[Path, ...]:
    return tuple(sorted(_POOLS_DIR.glob("*.json")))


def _numeric_version(version_id: str) -> int:
    suffix = version_id.rsplit("_v", 1)[-1] if "_v" in version_id else ""
    return int(suffix) if suffix.isdigit() else -1


def pool_for_market(
    market: Market,
    asset_class: AssetClass,
    underlying: AssetClass,
) -> SymbolPool | None:
    """Current default for a new research: highest numeric version of this market."""
    matches: list[SymbolPool] = []
    for path in list_pool_files():
        pool = _load_pool_file(path)
        if (
            pool.market is market
            and pool.asset_class is asset_class
            and pool.underlying_asset_class is underlying
        ):
            matches.append(pool)
    if not matches:
        return None
    return max(matches, key=lambda pool: (_numeric_version(pool.version_id), pool.version_id))


def pool_by_version(version_id: str) -> SymbolPool | None:
    for path in list_pool_files():
        pool = _load_pool_file(path)
        if pool.version_id == version_id:
            return pool
    return None


def pool_for_universe(
    market: Market,
    asset_class: AssetClass,
    underlying: AssetClass,
    symbol_list_version: str | None,
) -> SymbolPool | None:
    """Pinned version wins, so an old research does not pick up a newer default."""
    if symbol_list_version:
        pinned = pool_by_version(symbol_list_version)
        if pinned is not None:
            return pinned
    return pool_for_market(market, asset_class, underlying)


def _empty_pool_dialogue_prompt() -> str:
    us = pool_for_market(Market.US, AssetClass.EQUITY, AssetClass.EQUITY)
    cn = pool_for_market(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY)
    us_text = f"{us.display_name} {len(us.symbols)} 只" if us is not None else "美股大市值"
    cn_text = f"{cn.display_name} {len(cn.symbols)} 只" if cn is not None else "A股大市值"
    return (
        f"要用哪组标的？默认：{us_text}或 {cn_text}，也可以说「600519.SH」或「SPY、QQQ」。"
    )


EMPTY_POOL_DIALOGUE_PROMPT = _empty_pool_dialogue_prompt()
