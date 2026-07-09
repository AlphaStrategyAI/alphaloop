"""
OpenStrategy - An open-source quantitative investment research framework.

A simple, reliable framework for individual investors that prioritizes
honest evaluation over alpha promises.
"""

__version__ = "2.0.0"
__author__ = "OpenStrategy Team"

from .backtest import BacktestConfig, BacktestEngine
from .core import Asset, Portfolio, Position
from .data import AKShareSource, YahooFinanceSource
from .diagnostic import (
    deflated_sharpe,
    walk_forward_cv,
    data_source_consistency,
    vs_random,
    vs_buy_hold,
    vs_spy_buyhold,
)
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
    "deflated_sharpe",
    "walk_forward_cv",
    "data_source_consistency",
    "vs_random",
    "vs_buy_hold",
    "vs_spy_buyhold",
]
