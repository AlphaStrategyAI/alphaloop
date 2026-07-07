"""
目标日期策略 - Target Date Strategy

根据目标退休/使用年份自动调整股债比例（Glide Path）。
随着时间推移，逐渐降低股票比例，增加债券比例，降低组合风险。
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from ..core.portfolio import Portfolio
from .base import BaseStrategy, Signal

logger = logging.getLogger(__name__)


@dataclass
class GlidePathPoint:
    """Glide Path上的一个点"""
    year: int
    equity_ratio: float
    bond_ratio: float


class TargetDateStrategy(BaseStrategy):
    """
    目标日期策略 (Target Date / Glide Path Strategy)

    根据目标年份自动调整股债配置比例，实现从进取型向保守型的平滑过渡。
    这是退休基金和目标日期基金（Target Date Funds）最常用的策略。

    策略逻辑：
    1. 根据当前年龄和目标年份确定投资期限
    2. 使用Glide Path计算当前应有的股债比例
    3. 股票比例随时间线性下降，债券比例线性上升
    4. 到达目标年份后保持最终配置（通常是保守型）

    Glide Path公式：
    - 当前股票比例 = 初始股票比例 - (已过年数 / 总年数) × (初始比例 - 最终比例)
    - 债券比例 = 1 - 股票比例

    Examples:
        >>> # 2050年退休，当前30岁
        >>> strategy = TargetDateStrategy(
        ...     target_year=2050,
        ...     current_age=30,
        ...     final_equity_ratio=0.30,  # 退休时30%股票
        ... )
        
        >>> # 自定义初始配置
        >>> strategy = TargetDateStrategy(
        ...     target_year=2040,
        ...     current_age=40,
        ...     equity_symbol="VTI",
        ...     bond_symbol="BND",
        ...     final_equity_ratio=0.25,
        ... )

    Attributes:
        target_year: 目标年份（2025-2060）
        current_age: 当前年龄（25-60）
        final_equity_ratio: 目标年份时的股票比例（20-40%，默认30%）
        equity_symbol: 股票ETF代码（默认VTI）
        bond_symbol: 债券ETF代码（默认BND）
        initial_equity_ratio: 初始股票比例（自动计算）
        rebalance_frequency: 再平衡频率（"yearly"/"quarterly"）
        initial_investment: 初始投资金额
    
    Strategy Metadata:
        - 策略类型: 目标日期 / 生命周期
        - 预期年化收益: 6-12%（随时间递减）
        - 风险等级: 动态变化（高→中→低）
        - 最佳适用: 退休规划、教育基金
        - 理论基础: 生命周期投资理论
        - 代表产品: Vanguard Target Date Funds, Fidelity Freedom Funds
    """

    # 推荐的目标日期基金配置
    RECOMMENDED_CONFIG = {
        "aggressive": {"start_equity": 0.90, "final_equity": 0.30},   # 激进型
        "moderate": {"start_equity": 0.80, "final_equity": 0.35},    # 平衡型
        "conservative": {"start_equity": 0.70, "final_equity": 0.40}, # 保守型
    }

    def __init__(
        self,
        target_year: int,
        current_age: int,
        final_equity_ratio: float = 0.30,
        equity_symbol: str = "VTI",
        bond_symbol: str = "BND",
        rebalance_frequency: str = "yearly",
        initial_investment: float = 100000.0,
        name: str = "target_date",
    ):
        """
        初始化目标日期策略

        Args:
            target_year: 目标年份（2025-2060）
            current_age: 当前年龄（25-60）
            final_equity_ratio: 最终股票比例（0.20-0.40，默认0.30）
            equity_symbol: 股票ETF代码（默认VTI）
            bond_symbol: 债券ETF代码（默认BND）
            rebalance_frequency: 再平衡频率（"yearly"/"quarterly"）
            initial_investment: 初始投资金额
            name: 策略名称

        Raises:
            ValueError: 参数不合法时
        """
        super().__init__(name=name)
        
        current_year = datetime.now().year
        
        # 参数验证
        if not 2025 <= target_year <= 2060:
            raise ValueError(
                f"target_year must be between 2025 and 2060, got {target_year}"
            )
        
        if target_year <= current_year:
            raise ValueError(
                f"target_year ({target_year}) must be in the future, "
                f"current year is {current_year}"
            )
        
        if not 25 <= current_age <= 60:
            raise ValueError(
                f"current_age must be between 25 and 60, got {current_age}"
            )
        
        if not 0.20 <= final_equity_ratio <= 0.40:
            raise ValueError(
                f"final_equity_ratio must be between 20% and 40%, "
                f"got {final_equity_ratio:.1%}"
            )
        
        self.target_year = target_year
        self.current_age = current_age
        self.final_equity_ratio = final_equity_ratio
        self.equity_symbol = equity_symbol.upper()
        self.bond_symbol = bond_symbol.upper()
        self.rebalance_frequency = rebalance_frequency.lower()
        self.initial_investment = initial_investment
        
        # 计算投资期限
        self._investment_years = target_year - current_year
        
        # 计算初始股票比例（假设退休时65岁）
        retirement_age = 65
        years_to_retirement = retirement_age - current_age
        
        # 使用标准glide path: 从约90%股票开始（如果期限长）
        if years_to_retirement > 40:
            self.initial_equity_ratio = 0.90
        elif years_to_retirement > 20:
            self.initial_equity_ratio = 0.80
        else:
            self.initial_equity_ratio = 0.70
        
        # 内部状态
        self._last_rebalance: Optional[datetime] = None
        self._initial_allocation_done = False
        self._current_equity_ratio: float = self.initial_equity_ratio
        
        # 再平衡间隔天数
        self._frequency_days = {
            "yearly": 365,
            "quarterly": 91,
        }.get(self.rebalance_frequency, 365)
        
        # 策略元数据
        self._metadata = {
            "description": f"目标日期策略 - {target_year}年目标",
            "expected_return": "6-12% (decreasing over time)",
            "risk_level": "动态变化 (高→中→低)",
            "best_for": "退休规划、教育基金",
            "theoretical_basis": "生命周期投资理论",
            "years_to_target": self._investment_years,
        }
        
        logger.info(
            f"Initialized {self.name}: target={target_year}, "
            f"age={current_age}, glide path: {self.initial_equity_ratio:.0%}→{final_equity_ratio:.0%}"
        )

    def initialize(self, **kwargs) -> None:
        """初始化策略"""
        super().initialize(**kwargs)
        self._last_rebalance = None
        self._initial_allocation_done = False
        self._current_equity_ratio = self.initial_equity_ratio

    @property
    def symbols(self) -> List[str]:
        """获取策略使用的所有资产代码"""
        return [self.equity_symbol, self.bond_symbol]

    def _calculate_equity_ratio(self, current_date: datetime) -> float:
        """
        计算当前应持有的股票比例

        使用线性glide path公式：
        equity_ratio = initial - (elapsed_years / total_years) * (initial - final)

        Args:
            current_date: 当前日期

        Returns:
            当前股票比例
        """
        current_year = current_date.year
        
        # 如果已到达或超过目标年份
        if current_year >= self.target_year:
            return self.final_equity_ratio
        
        # 计算已过年数
        elapsed_years = current_year - (self.target_year - self._investment_years)
        elapsed_years = max(0, elapsed_years)
        
        # 线性插值
        if self._investment_years <= 0:
            return self.final_equity_ratio
        
        progress = elapsed_years / self._investment_years
        progress = min(1.0, max(0.0, progress))
        
        equity_ratio = (
            self.initial_equity_ratio
            - progress * (self.initial_equity_ratio - self.final_equity_ratio)
        )
        
        return equity_ratio

    def _should_rebalance(self, current_date: datetime) -> bool:
        """
        判断是否需要再平衡

        Args:
            current_date: 当前日期

        Returns:
            是否需要再平衡
        """
        if not self._initial_allocation_done:
            return True
        
        if self._last_rebalance is None:
            return True
        
        days_since = (current_date - self._last_rebalance).days
        return days_since >= self._frequency_days

    def get_target_weights(self, current_date: datetime) -> Dict[str, float]:
        """
        获取目标权重配置

        Args:
            current_date: 当前日期

        Returns:
            目标权重字典
        """
        equity_ratio = self._calculate_equity_ratio(current_date)
        bond_ratio = 1.0 - equity_ratio
        
        return {
            self.equity_symbol: equity_ratio,
            self.bond_symbol: bond_ratio,
        }

    def generate_signals(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
        current_date: Optional[datetime] = None,
    ) -> List[Signal]:
        """
        生成交易信号

        策略逻辑：
        1. 检查是否需要再平衡
        2. 根据当前日期计算glide path上的股债比例
        3. 计算目标持仓
        4. 生成再平衡信号

        Args:
            data: 历史价格数据
            portfolio: 当前投资组合
            current_date: 当前日期

        Returns:
            交易信号列表
        """
        signals = []
        
        if data.empty or current_date is None:
            return signals
        
        # 检查是否需要再平衡
        if not self._should_rebalance(current_date):
            return signals
        
        current_prices = data.iloc[-1].to_dict()
        
        # 计算当前目标配置
        target_weights = self.get_target_weights(current_date)
        self._current_equity_ratio = target_weights[self.equity_symbol]
        
        # 计算总资产价值
        if self._initial_allocation_done:
            total_value = portfolio.total_value(current_prices)
        else:
            total_value = self.initial_investment
        
        # 生成交易信号
        for symbol, target_weight in target_weights.items():
            if symbol not in current_prices:
                continue
            
            price = current_prices[symbol]
            if price <= 0:
                continue
            
            target_value = total_value * target_weight
            target_qty = target_value / price if price > 0 else 0
            
            # 当前持仓
            position = portfolio.get_position(symbol)
            current_qty = position.quantity if position else 0.0
            current_value = current_qty * price
            
            # 需要调整的数量
            delta_qty = target_qty - current_qty
            delta_value = abs(delta_qty) * price
            
            # 最小交易阈值（占总资产0.1%）
            if delta_value < 0.001 * total_value:
                continue
            
            action = "buy" if delta_qty > 0 else "sell"
            
            signals.append(
                Signal(
                    symbol=symbol,
                    action=action,
                    quantity=abs(delta_qty),
                    weight=target_weight,
                    price=price,
                    timestamp=current_date,
                    metadata={
                        "reason": "glide_path_rebalance" if self._initial_allocation_done else "initial_allocation",
                        "target_weight": target_weight,
                        "current_equity_ratio": self._current_equity_ratio,
                        "years_to_target": self.target_year - current_date.year,
                        "glide_path_progress": (
                            (self.initial_equity_ratio - self._current_equity_ratio)
                            / (self.initial_equity_ratio - self.final_equity_ratio)
                            if self.initial_equity_ratio != self.final_equity_ratio
                            else 1.0
                        ),
                    },
                )
            )
        
        if signals:
            self._last_rebalance = current_date
            self._initial_allocation_done = True
            logger.info(
                f"[{self.name}] {'Initial allocation' if not self._initial_allocation_done else 'Rebalanced'} "
                f"on {current_date.date()}: equity={self._current_equity_ratio:.1%}, "
                f"{self.target_year - current_date.year} years to target"
            )
        
        return signals

    def get_glide_path(self) -> List[GlidePathPoint]:
        """
        获取完整的Glide Path

        Returns:
            Glide Path点列表
        """
        path = []
        current_year = datetime.now().year
        start_year = max(current_year, self.target_year - self._investment_years)
        
        for year in range(start_year, self.target_year + 1):
            # 使用年初日期计算比例
            date = datetime(year, 1, 1)
            equity_ratio = self._calculate_equity_ratio(date)
            
            path.append(GlidePathPoint(
                year=year,
                equity_ratio=equity_ratio,
                bond_ratio=1.0 - equity_ratio,
            ))
        
        return path

    def get_allocation_at_year(self, year: int) -> Dict[str, float]:
        """
        获取指定年份的配置

        Args:
            year: 目标年份

        Returns:
            配置字典
        """
        date = datetime(year, 1, 1)
        return self.get_target_weights(date)

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
        return self._should_rebalance(current_date)

    def get_summary(self) -> Dict[str, Any]:
        """获取策略摘要"""
        return {
            "name": self.name,
            "type": "目标日期策略",
            "target_year": self.target_year,
            "current_age": self.current_age,
            "glide_path": {
                "start": f"{self.initial_equity_ratio:.0%} 股票",
                "end": f"{self.final_equity_ratio:.0%} 股票",
                "current": f"{self._current_equity_ratio:.0%} 股票",
            },
            "allocation": {
                self.equity_symbol: f"{self._current_equity_ratio:.0%}",
                self.bond_symbol: f"{1 - self._current_equity_ratio:.0%}",
            },
            "years_to_target": self.target_year - datetime.now().year,
            **self._metadata,
        }
