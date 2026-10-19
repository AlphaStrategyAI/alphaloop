"""User-visible A2 strings. One place for the i18n pass to turn into keys."""

from __future__ import annotations

from engine.research.models import AssetClass, Market, Research

US_EQUITY_CONSTRUCTION = "单票 ≤5%、成本 5 bp（保守产品假设）"
US_FUND_CONSTRUCTION = "基金腿不受单票 5% 上限约束、成本 1 bp（保守产品假设）"
CN_EQUITY_CONSTRUCTION = "单票 ≤5%、成本 20 bp（保守产品假设）"
CN_FUND_CONSTRUCTION = "基金腿不受单票 5% 上限约束、成本 5 bp（保守产品假设）"
CN_EXECUTION_NOTICE = "未模拟 T+1 与涨跌停，实际成交可能更差"


def construction_notice_for(research: Research) -> str | None:
    """Assumption the confirm card shows before a new run locks the schedule."""
    universe = research.brief.universe.value
    if universe is None:
        return None
    if universe.market is Market.US and universe.asset_class is AssetClass.EQUITY:
        return US_EQUITY_CONSTRUCTION
    if universe.market is Market.US and universe.asset_class is AssetClass.FUND:
        return US_FUND_CONSTRUCTION
    if universe.market is Market.CN and universe.asset_class is AssetClass.EQUITY:
        return CN_EQUITY_CONSTRUCTION
    if universe.market is Market.CN and universe.asset_class is AssetClass.FUND:
        return CN_FUND_CONSTRUCTION
    return None


def cn_execution_notice_for(research: Research) -> str | None:
    universe = research.brief.universe.value
    if universe is None or universe.market is not Market.CN:
        return None
    return CN_EXECUTION_NOTICE
