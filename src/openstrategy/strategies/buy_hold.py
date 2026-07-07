"""
买入持有策略 - 最简单的长期投资策略
"""

from datetime import datetime
from typing import List, Optional

import pandas as pd

from ..core.portfolio import Portfolio
from .base import BaseStrategy, Signal


class BuyHoldStrategy(BaseStrategy):
    """
    买入持有策略

    在开始时按目标权重买入资产，之后一直持有不动。
    这是最简单的被动投资策略，适合作为基准对比。

    Examples:
        >>> strategy = BuyHoldStrategy(
        ...     symbols=["VTI", "BND", "VXUS"],
        ...     weights=[0.6, 0.3, 0.1]
        ... )
        >>> signals = strategy.generate_signals(data, portfolio)

    Attributes:
        symbols: 资产列表
        weights: 目标权重
        initial_investment: 初始投资金额
    """

    def __init__(
        self,
        symbols: List[str],
        weights: Optional[List[float]] = None,
        initial_investment: float = 100000.0,
        name: str = "buy_hold",
    ):
        """
        初始化买入持有策略

        Args:
            symbols: 资产代码列表
            weights: 权重列表（默认等权）
            initial_investment: 初始投资金额
            name: 策略名称
        """
        super().__init__(name=name)
        self.symbols = [s.upper() for s in symbols]

        # 默认等权
        if weights is None:
            n = len(symbols)
            self.weights = [1.0 / n] * n if n > 0 else []
        else:
            # 归一化权重
            total = sum(weights)
            self.weights = [w / total for w in weights]

        self.initial_investment = initial_investment
        self._has_initialized = False

    def initialize(self, **kwargs) -> None:
        """初始化策略"""
        super().initialize(**kwargs)
        self._has_initialized = False

    def generate_signals(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
        current_date: Optional[datetime] = None,
    ) -> List[Signal]:
        """
        生成信号 - 只在开始时买入一次

        Args:
            data: 价格数据
            portfolio: 当前组合
            current_date: 当前日期

        Returns:
            买入信号列表（仅第一次调用）
        """
        signals = []

        # 只在开始时生成一次信号
        if self._has_initialized:
            return signals

        self._has_initialized = True

        # 获取当前价格
        if data.empty:
            return signals

        current_prices = data.iloc[-1].to_dict()

        # 生成买入信号
        for symbol, weight in zip(self.symbols, self.weights):
            if symbol not in current_prices:
                continue

            price = current_prices[symbol]
            if price <= 0:
                continue

            # 计算购买数量
            target_value = self.initial_investment * weight
            quantity = target_value / price

            signals.append(
                Signal(
                    symbol=symbol,
                    action="buy",
                    quantity=quantity,
                    weight=weight,
                    price=price,
                    timestamp=current_date,
                    metadata={"reason": "initial_allocation"},
                )
            )

        return signals

    def get_target_weights(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> dict:
        """获取目标权重"""
        return {s: w for s, w in zip(self.symbols, self.weights)}
