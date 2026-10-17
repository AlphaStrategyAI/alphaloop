"""Versioned, checked-in symbol pools — never chosen at runtime by a model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from engine.research.models import AssetClass, Market

_POOLS_DIR = Path(__file__).resolve().parent / "symbol_pools"

EMPTY_POOL_DIALOGUE_PROMPT = (
    "要用哪组标的？默认：美股大市值 40 只，也可以说「SPY、QQQ」。"
)


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


def pool_for_market(
    market: Market,
    asset_class: AssetClass,
    underlying: AssetClass,
) -> SymbolPool | None:
    for path in list_pool_files():
        pool = _load_pool_file(path)
        if (
            pool.market is market
            and pool.asset_class is asset_class
            and pool.underlying_asset_class is underlying
        ):
            return pool
    return None


def pool_by_version(version_id: str) -> SymbolPool | None:
    for path in list_pool_files():
        pool = _load_pool_file(path)
        if pool.version_id == version_id:
            return pool
    return None
