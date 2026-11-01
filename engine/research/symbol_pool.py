"""Versioned, checked-in symbol pools — never chosen at runtime by a model."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
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
    actual_available_at: str | None = None
    source_fingerprint: str | None = None


@lru_cache(maxsize=16)
def _load_pool_file(path: Path) -> SymbolPool:
    raw = json.loads(path.read_text(encoding="utf-8"))
    symbols = tuple(str(s) for s in raw["symbols"])
    fingerprint = raw.get("source_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint:
        fingerprint = hashlib.sha256(
            ("\n".join(symbols) + "\n" + str(raw.get("version_id", ""))).encode("utf-8")
        ).hexdigest()
    available = raw.get("actual_available_at")
    return SymbolPool(
        version_id=str(raw["version_id"]),
        display_name=str(raw["display_name"]).replace("A股", "A 股"),
        generated_date=str(raw["generated_date"]),
        market=Market(raw["market"]),
        asset_class=AssetClass(raw["asset_class"]),
        underlying_asset_class=AssetClass(raw["underlying_asset_class"]),
        symbols=symbols,
        actual_available_at=str(available) if isinstance(available, str) and available else None,
        source_fingerprint=fingerprint,
    )


def list_pool_files() -> tuple[Path, ...]:
    return tuple(sorted(_POOLS_DIR.glob("*.json")))


def _numeric_version(version_id: str) -> int:
    suffix = version_id.rsplit("_v", 1)[-1] if "_v" in version_id else ""
    return int(suffix) if suffix.isdigit() else -1


def _matches_market(
    pool: SymbolPool,
    market: Market,
    asset_class: AssetClass,
    underlying: AssetClass,
) -> bool:
    return (
        pool.market is market
        and pool.asset_class is asset_class
        and pool.underlying_asset_class is underlying
    )


def pool_final_grade(pool: SymbolPool | None, as_of: date) -> tuple[str, str]:
    """Final evaluation needs a constituent list known on or before ``as_of``."""
    if pool is None or not pool.actual_available_at:
        return ("exploratory", "成分名单的实际可得日未知，只能作为探索级")
    try:
        available = date.fromisoformat(pool.actual_available_at)
    except ValueError:
        return ("exploratory", "成分名单的实际可得日无法解析，只能作为探索级")
    if available > as_of:
        return ("exploratory", "成分名单晚于探索截止日，只能作为探索级")
    return ("final", "")


def pool_for_market(
    market: Market,
    asset_class: AssetClass,
    underlying: AssetClass,
    *,
    as_of: date | None = None,
    pools: tuple[SymbolPool, ...] | None = None,
) -> SymbolPool | None:
    """Current default for a new research: highest numeric version of this market.

    ``as_of`` keeps only lists whose ``actual_available_at`` is on or before that
    day. A missing date is not treated as available. No match degrades to no pool.
    """
    matches: list[SymbolPool] = []
    source = pools if pools is not None else tuple(_load_pool_file(path) for path in list_pool_files())
    for pool in source:
        if _matches_market(pool, market, asset_class, underlying):
            matches.append(pool)
    if as_of is not None:
        eligible: list[SymbolPool] = []
        for pool in matches:
            grade, _reason = pool_final_grade(pool, as_of)
            if grade == "final":
                eligible.append(pool)
        matches = eligible
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


def _pool_prompt_label(pool: SymbolPool | None, fallback: str) -> str:
    if pool is None:
        return fallback
    from engine.research.pool_display import public_pool_copy

    copy = public_pool_copy(pool.version_id, len(pool.symbols), pool.generated_date)
    if copy is not None:
        return copy["zh"]
    return f"{pool.display_name} {len(pool.symbols)} 只"


def _empty_pool_dialogue_prompt() -> str:
    us = pool_for_market(Market.US, AssetClass.EQUITY, AssetClass.EQUITY)
    cn = pool_for_market(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY)
    us_text = _pool_prompt_label(us, "美股大市值")
    cn_text = _pool_prompt_label(cn, "A 股大市值")
    return (
        f"要用哪组标的？默认：{us_text}或 {cn_text}，也可以说「600519.SH」或「SPY、QQQ」。"
    )


EMPTY_POOL_DIALOGUE_PROMPT = _empty_pool_dialogue_prompt()
