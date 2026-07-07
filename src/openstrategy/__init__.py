"""
OpenStrategy - 开源量化投资策略框架

一个简单、可靠、适合普通投资者的投资策略系统。
"""

__version__ = "2.0.0"
__author__ = "OpenStrategy Team"

from .backtest import BacktestConfig, BacktestEngine
from .core import Asset, Portfolio, Position
from .data import AKShareSource, YahooFinanceSource
from .strategies import BuyHoldStrategy, RebalanceStrategy, StrategyFactory

__all__ = [
    "Portfolio",
    "Asset",
    "Position",
    "BuyHoldStrategy",
    "RebalanceStrategy",
    "StrategyFactory",
    "BacktestEngine",
    "BacktestConfig",
    "YahooFinanceSource",
    "AKShareSource",
]
