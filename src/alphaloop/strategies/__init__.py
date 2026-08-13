"""
Strategy Layer - 投资策略
"""

from .base import BaseStrategy, StrategyResult
from .buy_hold import BuyHoldStrategy
from .classic_6040 import Classic6040Strategy
from .factory import StrategyFactory
from .global_multi_asset import (
    AssetMapping,
    GlobalMultiAssetStrategy,
    RebalanceTrigger,
    RegionalAllocation,
    TacticalMethod,
)
from .moving_average import MovingAverageCrossoverStrategy
from .rebalance import RebalanceStrategy
from .risk_parity import RiskParityStrategy
from .sector_rotation import SectorRotationStrategy, SECTOR_ETFS
from .target_date import TargetDateStrategy
from .value_strategy import ValueStrategy

__all__ = [
    "BaseStrategy",
    "StrategyResult",
    "BuyHoldStrategy",
    "RebalanceStrategy",
    "GlobalMultiAssetStrategy",
    "RebalanceTrigger",
    "TacticalMethod",
    "RegionalAllocation",
    "AssetMapping",
    "StrategyFactory",
    # Phase 2.1 新增策略
    "MovingAverageCrossoverStrategy",
    "Classic6040Strategy",
    "ValueStrategy",
    # Phase 2.1 新增策略（剩余3个）
    "SectorRotationStrategy",
    "SECTOR_ETFS",
    "RiskParityStrategy",
    "TargetDateStrategy",
]

# 注册内置策略（在避免循环导入后）
StrategyFactory.register("buy_hold", BuyHoldStrategy)
StrategyFactory.register("rebalance", RebalanceStrategy)
StrategyFactory.register("global_multi_asset", GlobalMultiAssetStrategy)
# Phase 2.1 新增策略注册
StrategyFactory.register("ma_crossover", MovingAverageCrossoverStrategy)
StrategyFactory.register("classic_6040", Classic6040Strategy)
StrategyFactory.register("value_strategy", ValueStrategy)
# Phase 2.1 剩余策略注册
StrategyFactory.register("sector_rotation", SectorRotationStrategy)
StrategyFactory.register("risk_parity", RiskParityStrategy)
StrategyFactory.register("target_date", TargetDateStrategy)
