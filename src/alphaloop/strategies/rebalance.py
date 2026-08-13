"""
再平衡策略 - 定期或阈值触发的资产配置再平衡
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from ..core.enums import RebalanceMethod
from ..core.portfolio import Portfolio
from .base import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class RebalanceStrategy(BaseStrategy):
    """
    再平衡策略

    支持多种再平衡触发机制：
    - THRESHOLD: 阈值触发（当偏离超过阈值时）
    - CALENDAR: 日历触发（定期再平衡）
    - CALENDAR_AND_THRESHOLD: 两者结合

    Examples:
        >>> strategy = RebalanceStrategy(
        ...     symbols=["VTI", "BND", "VXUS"],
        ...     weights=[0.6, 0.3, 0.1],
        ...     method=RebalanceMethod.THRESHOLD,
        ...     threshold=0.05,  # 偏离5%时触发
        ... )

    Attributes:
        symbols: 资产列表
        weights: 目标权重
        method: 再平衡方法
        threshold: 偏离阈值（THRESHOLD方法用）
        frequency_days: 再平衡频率（CALENDAR方法用）
        tolerance: 最小交易阈值（避免微小交易）
    """

    def __init__(
        self,
        symbols: List[str],
        weights: Optional[List[float]] = None,
        method: RebalanceMethod = RebalanceMethod.THRESHOLD,
        threshold: float = 0.05,
        frequency_days: int = 30,
        tolerance: float = 0.001,
        name: str = "rebalance",
    ):
        """
        初始化再平衡策略

        Args:
            symbols: 资产代码列表
            weights: 目标权重（默认等权）
            method: 再平衡方法
            threshold: 偏离阈值（0.05 = 5%）
            frequency_days: 再平衡频率（天）
            tolerance: 最小交易阈值（相对总资产）
            name: 策略名称
        """
        super().__init__(name=name)
        self.symbols = [s.upper() for s in symbols]

        # 默认等权
        if weights is None:
            n = len(symbols)
            self.weights = [1.0 / n] * n if n > 0 else []
        else:
            # 归一化
            total = sum(weights)
            self.weights = [w / total for w in weights]

        self.method = method
        self.threshold = threshold
        self.frequency_days = frequency_days
        self.tolerance = tolerance

        self._last_rebalance: Optional[datetime] = None
        self._initial_allocation_done = False

    def initialize(self, **kwargs) -> None:
        """初始化策略"""
        super().initialize(**kwargs)
        self._last_rebalance = None
        self._initial_allocation_done = False

    def generate_signals(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
        current_date: Optional[datetime] = None,
    ) -> List[Signal]:
        """
        生成再平衡信号

        Args:
            data: 价格数据
            portfolio: 当前组合
            current_date: 当前日期

        Returns:
            交易信号列表
        """
        if data.empty or current_date is None:
            return []

        signals = []
        current_prices = data.iloc[-1].to_dict()
        target_weights = {s: w for s, w in zip(self.symbols, self.weights)}

        # 1. 初始配置
        if not self._initial_allocation_done:
            signals = self._generate_initial_signals(current_prices, current_date)
            self._initial_allocation_done = True
            self._last_rebalance = current_date
            return signals

        # 2. 检查是否需要再平衡
        if not self._should_rebalance(portfolio, current_prices, current_date):
            return []

        # 3. 生成再平衡信号
        signals = self._generate_rebalance_signals(
            portfolio, target_weights, current_prices, current_date
        )

        if signals:
            self._last_rebalance = current_date
            logger.info(f"Rebalanced on {current_date.date()}: {len(signals)} trades")

        return signals

    def _should_rebalance(
        self,
        portfolio: Portfolio,
        prices: Dict[str, float],
        current_date: datetime,
    ) -> bool:
        """判断是否需要再平衡"""

        # 日历触发
        if self.method in (RebalanceMethod.CALENDAR, RebalanceMethod.CALENDAR_AND_THRESHOLD):
            if self._last_rebalance is None:
                return True
            days_since = (current_date - self._last_rebalance).days
            if days_since >= self.frequency_days:
                return True

        # 阈值触发
        if self.method in (RebalanceMethod.THRESHOLD, RebalanceMethod.CALENDAR_AND_THRESHOLD):
            max_dev = portfolio.max_deviation(
                {s: w for s, w in zip(self.symbols, self.weights)}, prices
            )
            if max_dev >= self.threshold:
                return True

        return False

    def _generate_initial_signals(
        self,
        prices: Dict[str, float],
        current_date: datetime,
    ) -> List[Signal]:
        """生成初始配置信号"""
        signals = []
        total_value = (
            sum(self.initial_investment for _ in self.symbols)
            / len(self.symbols)
            * len(self.symbols)
        )

        for symbol, weight in zip(self.symbols, self.weights):
            if symbol not in prices:
                continue

            price = prices[symbol]
            if price <= 0:
                continue

            target_value = total_value * weight
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

    def _generate_rebalance_signals(
        self,
        portfolio: Portfolio,
        target_weights: Dict[str, float],
        prices: Dict[str, float],
        current_date: datetime,
    ) -> List[Signal]:
        """生成再平衡信号"""
        signals = []
        total_value = portfolio.total_value(prices)

        if total_value <= 0:
            return signals

        for symbol, target_weight in target_weights.items():
            if symbol not in prices:
                continue

            price = prices[symbol]
            if price <= 0:
                continue

            # 当前持仓
            current_pos = portfolio.get_position(symbol)
            current_qty = current_pos.quantity if current_pos else 0.0
            current_value = current_qty * price
            current_weight = current_value / total_value if total_value > 0 else 0.0

            # 目标持仓
            target_value = total_value * target_weight
            target_qty = target_value / price

            # 需要调整的数量
            delta_qty = target_qty - current_qty
            delta_value = abs(delta_qty) * price

            # 检查是否超过最小交易阈值
            if delta_value < self.tolerance * total_value:
                continue

            # 生成信号
            if delta_qty > 0:
                signals.append(
                    Signal(
                        symbol=symbol,
                        action="buy",
                        quantity=delta_qty,
                        weight=target_weight,
                        price=price,
                        timestamp=current_date,
                        metadata={
                            "reason": "rebalance",
                            "current_weight": current_weight,
                            "target_weight": target_weight,
                            "deviation": current_weight - target_weight,
                        },
                    )
                )
            elif delta_qty < 0:
                signals.append(
                    Signal(
                        symbol=symbol,
                        action="sell",
                        quantity=abs(delta_qty),
                        weight=target_weight,
                        price=price,
                        timestamp=current_date,
                        metadata={
                            "reason": "rebalance",
                            "current_weight": current_weight,
                            "target_weight": target_weight,
                            "deviation": current_weight - target_weight,
                        },
                    )
                )

        return signals

    def get_target_weights(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> Dict[str, float]:
        """获取目标权重"""
        return {s: w for s, w in zip(self.symbols, self.weights)}

    @property
    def initial_investment(self) -> float:
        """初始投资金额（从参数获取）"""
        return self.params.get("initial_investment", 100000.0)
