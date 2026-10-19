"""User-visible A2 strings. One place for the i18n pass to turn into keys."""

from __future__ import annotations

from engine.portfolio import NAME_CAP_MIN_HOLDABLE
from engine.research.models import AssetClass, Market, Research

US_EQUITY_COST = "成本 5 bp（保守产品假设）"
CN_EQUITY_COST = "成本 20 bp（保守产品假设）"
US_FUND_COST = "成本 1 bp（保守产品假设）"
CN_FUND_COST = "成本 5 bp（保守产品假设）"
NAME_CAP_PREFIX = "单票 ≤5%、"
US_EQUITY_CONSTRUCTION = NAME_CAP_PREFIX + US_EQUITY_COST
CN_EQUITY_CONSTRUCTION = NAME_CAP_PREFIX + CN_EQUITY_COST
US_FUND_CONSTRUCTION = "基金腿不受单票 5% 上限约束、" + US_FUND_COST
CN_FUND_CONSTRUCTION = "基金腿不受单票 5% 上限约束、" + CN_FUND_COST
CN_EXECUTION_NOTICE = "未模拟 T+1 与涨跌停，实际成交可能更差"


def _equity_notice(cost: str, holdable: int) -> str:
    if holdable >= NAME_CAP_MIN_HOLDABLE:
        return NAME_CAP_PREFIX + cost
    return cost


def construction_notice_for(research: Research) -> str | None:
    """Confirm-card line from the symbols this research can actually hold.

    The count is ``universe.symbols`` after the pool is materialized and after
    any data probe has already dropped names. It is not the pool file's length.
    """
    universe = research.brief.universe.value
    if universe is None:
        return None
    holdable = len(universe.symbols)
    if universe.market is Market.US and universe.asset_class is AssetClass.EQUITY:
        return _equity_notice(US_EQUITY_COST, holdable)
    if universe.market is Market.US and universe.asset_class is AssetClass.FUND:
        return US_FUND_CONSTRUCTION
    if universe.market is Market.CN and universe.asset_class is AssetClass.EQUITY:
        return _equity_notice(CN_EQUITY_COST, holdable)
    if universe.market is Market.CN and universe.asset_class is AssetClass.FUND:
        return CN_FUND_CONSTRUCTION
    return None


def cn_execution_notice_for(research: Research) -> str | None:
    universe = research.brief.universe.value
    if universe is None or universe.market is not Market.CN:
        return None
    return CN_EXECUTION_NOTICE
