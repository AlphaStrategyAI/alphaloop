"""
目标函数 - 定义优化目标
"""

from dataclasses import dataclass
from typing import Callable

from ..backtest.engine import BacktestResult


@dataclass
class ObjectiveFunction:
    """
    优化目标函数

    用于参数优化时指定优化目标

    Examples:
        >>> # 最大化夏普比率
        >>> obj = ObjectiveFunction.maximize("sharpe_ratio")
        >>>
        >>> # 最小化最大回撤
        >>> obj = ObjectiveFunction.minimize("max_drawdown")
        >>>
        >>> # 自定义目标
        >>> def custom(result):
        ...     return result.metrics.sharpe_ratio / (result.metrics.max_drawdown + 0.01)
        >>> obj = ObjectiveFunction("custom", custom, maximize=True)
    """

    name: str
    func: Callable[[BacktestResult], float]
    maximize: bool = True

    def __call__(self, result: BacktestResult) -> float:
        """调用目标函数"""
        return self.func(result)

    @classmethod
    def maximize(cls, metric: str) -> "ObjectiveFunction":
        """最大化某个指标"""
        return cls(
            name=f"max_{metric}",
            func=lambda r: getattr(r.metrics, metric, 0.0),
            maximize=True,
        )

    @classmethod
    def minimize(cls, metric: str) -> "ObjectiveFunction":
        """最小化某个指标"""
        return cls(
            name=f"min_{metric}",
            func=lambda r: getattr(r.metrics, metric, 0.0),
            maximize=False,
        )

    @classmethod
    def risk_adjusted_return(cls) -> "ObjectiveFunction":
        """
        风险调整收益目标

        夏普比率 / (最大回撤 + 0.01)
        """

        def calc(result: BacktestResult) -> float:
            sharpe = result.metrics.sharpe_ratio
            max_dd = result.metrics.max_drawdown
            return sharpe / (max_dd + 0.01) if max_dd > 0 else sharpe

        return cls(
            name="risk_adjusted_return",
            func=calc,
            maximize=True,
        )

    @classmethod
    def calmar_ratio(cls) -> "ObjectiveFunction":
        """Calmar 比率目标"""
        return cls(
            name="calmar_ratio",
            func=lambda r: r.metrics.calmar_ratio,
            maximize=True,
        )
