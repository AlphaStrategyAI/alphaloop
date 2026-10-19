"""Closed strategy-family registry. Records store ids; display names are rendered."""

from __future__ import annotations

PRODUCT_FAMILY_IDS: tuple[str, ...] = (
    "low_volatility",
    "stock_bond_rebalance",
    "mean_reversion",
    "fundamental_factor",
    "all_weather",
)
LEGACY_FAMILY_ID = "legacy_mean_reversion"
FAMILY_IDS: tuple[str, ...] = PRODUCT_FAMILY_IDS + (LEGACY_FAMILY_ID,)

LEGACY_STRATEGY_FAMILY = "mean_reversion"
LEGACY_FAMILY_METHOD = "legacy_zscore_daily"

# Chinese source copy from the family spec. Not written into research records.
_ZH_DISPLAY = {
    "low_volatility": "低波",
    "stock_bond_rebalance": "股债再平衡",
    "mean_reversion": "均值回归",
    "fundamental_factor": "基本面因子",
    "all_weather": "全天候",
    "legacy_mean_reversion": LEGACY_FAMILY_ID,
}


def require_family_id(family_id: str) -> str:
    if family_id not in FAMILY_IDS:
        raise ValueError(f"unknown strategy family: {family_id}")
    return family_id


def family_display_name(family_id: str, locale: str) -> str:
    """Render a display name from the id. The id itself is what gets stored."""
    require_family_id(family_id)
    if locale.lower().startswith("zh"):
        return _ZH_DISPLAY[family_id]
    return family_id


def is_legacy_mean_reversion(strategy_family: str, family_method: str) -> bool:
    """V1 execution path: the old daily z-score mean reversion, not a new family card."""
    return (
        strategy_family in {LEGACY_STRATEGY_FAMILY, LEGACY_FAMILY_ID}
        and family_method == LEGACY_FAMILY_METHOD
    )
