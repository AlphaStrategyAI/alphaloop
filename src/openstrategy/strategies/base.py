"""
策略基类 - 定义统一策略接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from ..core.portfolio import Portfolio


@dataclass
class Signal:
    """
    交易信号

    Attributes:
        symbol: 资产代码
        action: 操作 ("buy", "sell", "hold")
        quantity: 数量（可选，None表示按权重）
        weight: 目标权重（0-1）
        price: 参考价格
        timestamp: 信号时间
        metadata: 额外信息
    """

    symbol: str
    action: str  # "buy", "sell", "hold"
    quantity: Optional[float] = None
    weight: float = 0.0
    price: float = 0.0
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyResult:
    """
    策略执行结果

    Attributes:
        portfolio: 最终投资组合
        signals: 生成的所有信号
        history: 历史持仓记录
        metrics: 策略指标
    """

    portfolio: Portfolio
    signals: List[Signal] = field(default_factory=list)
    history: pd.DataFrame = field(default_factory=pd.DataFrame)
    metrics: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> dict:
        """获取结果摘要"""
        return {
            "final_value": self.metrics.get("final_value", 0),
            "total_return": self.metrics.get("total_return", 0),
            "n_signals": len(self.signals),
            "n_trades": len([s for s in self.signals if s.action != "hold"]),
        }


class BaseStrategy(ABC):
    """
    策略基类

    所有投资策略都必须继承此类并实现 generate_signals 方法。

    Examples:
        >>> class MyStrategy(BaseStrategy):
        ...     def generate_signals(self, data, portfolio):
        ...         # 实现信号生成逻辑
        ...         return [Signal("AAPL", "buy", weight=0.5)]
    """

    def __init__(self, name: str = "base", params: Optional[Dict[str, Any]] = None):
        """
        初始化策略

        Args:
            name: 策略名称
            params: 策略参数字典
        """
        self.name = name
        self.params = params or {}
        self._initialized = False

    def initialize(self, **kwargs) -> None:
        """
        策略初始化

        在回测开始前调用，用于设置初始状态
        """
        self._initialized = True

    @abstractmethod
    def generate_signals(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
        current_date: Optional[datetime] = None,
    ) -> List[Signal]:
        """
        生成交易信号

        Args:
            data: 历史价格数据 (DataFrame with columns = symbols)
            portfolio: 当前投资组合
            current_date: 当前日期

        Returns:
            交易信号列表
        """
        pass

    def on_data(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
        current_date: Optional[datetime] = None,
    ) -> List[Signal]:
        """
        数据更新时的回调

        Args:
            data: 历史价格数据
            portfolio: 当前投资组合
            current_date: 当前日期

        Returns:
            交易信号列表
        """
        if not self._initialized:
            self.initialize()

        return self.generate_signals(data, portfolio, current_date)

    def get_target_weights(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> Dict[str, float]:
        """
        获取目标权重（用于再平衡策略）

        Args:
            data: 价格数据
            portfolio: 当前组合

        Returns:
            目标权重字典 {symbol: weight}
        """
        # 默认等权
        symbols = data.columns.tolist()
        n = len(symbols)
        return {s: 1.0 / n for s in symbols} if n > 0 else {}

    def should_rebalance(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
        current_date: datetime,
        last_rebalance: Optional[datetime] = None,
    ) -> bool:
        """
        判断是否需要再平衡

        Args:
            data: 价格数据
            portfolio: 当前组合
            current_date: 当前日期
            last_rebalance: 上次再平衡日期

        Returns:
            是否需要再平衡
        """
        # 默认定期检查（月度）
        if last_rebalance is None:
            return True

        days_since = (current_date - last_rebalance).days
        return days_since >= 30  # 默认30天再平衡一次

    def get_params(self) -> Dict[str, Any]:
        """获取策略参数"""
        return self.params.copy()

    def set_params(self, **params) -> None:
        """设置策略参数"""
        self.params.update(params)

    def copy(self) -> "BaseStrategy":
        """创建策略副本"""
        import copy

        return copy.deepcopy(self)
