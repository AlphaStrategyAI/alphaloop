"""
行业轮动策略 - Sector Rotation Strategy

基于行业ETF的相对动量进行定期轮动，投资动量最强的N个行业。
通过在经济周期不同阶段配置表现最佳的行业来获取超额收益。
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..core.portfolio import Portfolio
from .base import BaseStrategy, Signal

logger = logging.getLogger(__name__)


# 常用行业ETF定义
SECTOR_ETFS = {
    "XLK": {"name": "Technology", "description": "科技", "category": "growth"},
    "XLF": {"name": "Financials", "description": "金融", "category": "cyclical"},
    "XLE": {"name": "Energy", "description": "能源", "category": "cyclical"},
    "XLI": {"name": "Industrials", "description": "工业", "category": "cyclical"},
    "XLP": {"name": "Consumer Staples", "description": "消费必需品", "category": "defensive"},
    "XLU": {"name": "Utilities", "description": "公用事业", "category": "defensive"},
    "XLV": {"name": "Health Care", "description": "医疗保健", "category": "defensive"},
    "XLB": {"name": "Materials", "description": "材料", "category": "cyclical"},
    "XLC": {"name": "Communication Services", "description": "通信服务", "category": "growth"},
    "XLRE": {"name": "Real Estate", "description": "房地产", "category": "defensive"},
}


@dataclass
class SectorMomentum:
    """行业动量数据"""
    symbol: str
    momentum: float
    return_pct: float
    rank: int = 0


class SectorRotationStrategy(BaseStrategy):
    """
    行业轮动策略

    基于行业ETF的相对动量进行定期轮动，投资动量最强的N个行业。
    策略逻辑：
    1. 计算各行业的动量（回望期内的收益率）
    2. 选择动量最强的N个行业
    3. 等权重配置选中的行业
    4. 定期再平衡（如月度、季度）

    行业轮动是经典的主动管理策略，利用不同行业在经济周期不同阶段的表现差异。

    Examples:
        >>> # 使用默认行业ETF，选前3强
        >>> strategy = SectorRotationStrategy(
        ...     rotation_count=3,
        ...     lookback_period=3,  # 3个月回望期
        ... )
        
        >>> # 自定义行业ETF
        >>> strategy = SectorRotationStrategy(
        ...     sector_etfs=["XLK", "XLF", "XLE", "XLI"],
        ...     rotation_count=2,
        ...     lookback_period=6,  # 6个月回望期
        ... )

    Attributes:
        sector_etfs: 行业ETF代码列表
        rotation_count: 每次轮动的行业数量（3-5）
        lookback_period: 动量回望期，单位月（1-6）
        rebalance_frequency: 再平衡频率（"monthly", "quarterly"）
        initial_investment: 初始投资金额
        equal_weight: 是否等权重配置（默认True）
    
    Strategy Metadata:
        - 策略类型: 行业轮动 / 动量
        - 预期年化收益: 10-15%
        - 风险等级: 中高
        - 最佳市场环境: 行业分化明显的市场
        - 理论基础: 动量效应、行业周期轮动
    """

    def __init__(
        self,
        sector_etfs: Optional[List[str]] = None,
        rotation_count: int = 3,
        lookback_period: int = 3,
        rebalance_frequency: str = "monthly",
        initial_investment: float = 100000.0,
        equal_weight: bool = True,
        name: str = "sector_rotation",
    ):
        """
        初始化行业轮动策略

        Args:
            sector_etfs: 行业ETF代码列表（默认使用7个核心行业）
            rotation_count: 轮动的行业数量（3-5，默认3）
            lookback_period: 动量回望期月数（1-6，默认3）
            rebalance_frequency: 再平衡频率（"monthly"/"quarterly"，默认monthly）
            initial_investment: 初始投资金额
            equal_weight: 是否等权重配置
            name: 策略名称

        Raises:
            ValueError: 参数不合法时
        """
        super().__init__(name=name)
        
        # 默认使用7个核心行业ETF
        if sector_etfs is None:
            self.sector_etfs = ["XLK", "XLF", "XLE", "XLI", "XLP", "XLU", "XLV"]
        else:
            self.sector_etfs = [s.upper() for s in sector_etfs]
        
        # 参数验证
        if not 1 <= rotation_count <= len(self.sector_etfs):
            raise ValueError(
                f"rotation_count must be between 1 and {len(self.sector_etfs)}, "
                f"got {rotation_count}"
            )
        
        if not 1 <= lookback_period <= 6:
            raise ValueError(
                f"lookback_period must be between 1 and 6 months, "
                f"got {lookback_period}"
            )
        
        self.rotation_count = rotation_count
        self.lookback_period = lookback_period
        self.rebalance_frequency = rebalance_frequency.lower()
        self.initial_investment = initial_investment
        self.equal_weight = equal_weight
        
        # 内部状态
        self._last_rebalance: Optional[datetime] = None
        self._current_selection: List[str] = []
        self._initial_allocation_done = False
        
        # 再平衡间隔天数
        self._frequency_days = {
            "monthly": 30,
            "quarterly": 91,
        }.get(self.rebalance_frequency, 30)
        
        # 策略元数据
        self._metadata = {
            "description": "行业轮动策略 - 投资动量最强的行业",
            "expected_return": "10-15%",
            "risk_level": "中高",
            "best_market": "行业分化明显的市场",
            "theoretical_basis": "动量效应、行业周期轮动",
        }
        
        logger.info(
            f"Initialized {self.name}: top-{rotation_count} of {len(self.sector_etfs)} sectors, "
            f"{lookback_period}m lookback, {rebalance_frequency} rebalance"
        )

    def initialize(self, **kwargs) -> None:
        """初始化策略"""
        super().initialize(**kwargs)
        self._last_rebalance = None
        self._current_selection = []
        self._initial_allocation_done = False

    @property
    def symbols(self) -> List[str]:
        """获取策略使用的所有资产代码"""
        return self.sector_etfs.copy()

    def _calculate_momentum(self, data: pd.DataFrame, symbol: str) -> Optional[float]:
        """
        计算行业动量

        Args:
            data: 历史价格数据
            symbol: 行业ETF代码

        Returns:
            动量值（回望期收益率），数据不足时返回None
        """
        if symbol not in data.columns:
            return None
        
        price_series = data[symbol].dropna()
        
        # 计算回望期所需的交易天数（约21个交易日/月）
        lookback_days = self.lookback_period * 21
        
        if len(price_series) < lookback_days + 1:
            return None
        
        # 获取回望期前后的价格
        current_price = price_series.iloc[-1]
        past_price = price_series.iloc[-(lookback_days + 1)]
        
        if past_price <= 0:
            return None
        
        # 计算收益率
        momentum = (current_price - past_price) / past_price
        return momentum

    def _select_top_sectors(self, data: pd.DataFrame) -> List[SectorMomentum]:
        """
        选择动量最强的行业

        Args:
            data: 历史价格数据

        Returns:
            按动量排序的行业列表
        """
        momentum_list = []
        
        for symbol in self.sector_etfs:
            momentum = self._calculate_momentum(data, symbol)
            if momentum is not None:
                momentum_list.append(SectorMomentum(
                    symbol=symbol,
                    momentum=momentum,
                    return_pct=momentum * 100,
                ))
        
        # 按动量排序
        momentum_list.sort(key=lambda x: x.momentum, reverse=True)
        
        # 添加排名
        for i, item in enumerate(momentum_list):
            item.rank = i + 1
        
        return momentum_list

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

    def _get_allocation_weights(self, selected_sectors: List[str]) -> Dict[str, float]:
        """
        获取配置权重

        Args:
            selected_sectors: 选中的行业列表

        Returns:
            权重字典
        """
        if not selected_sectors:
            return {}
        
        if self.equal_weight:
            weight = 1.0 / len(selected_sectors)
            return {symbol: weight for symbol in selected_sectors}
        else:
            # 可以在这里实现基于动量的加权
            # 暂时使用等权
            weight = 1.0 / len(selected_sectors)
            return {symbol: weight for symbol in selected_sectors}

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
        2. 计算各行业动量
        3. 选择动量最强的N个行业
        4. 生成买入/卖出信号调整持仓

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
        
        # 选择动量最强的行业
        momentum_ranking = self._select_top_sectors(data)
        
        if len(momentum_ranking) < self.rotation_count:
            logger.warning(
                f"Not enough sectors with momentum data: {len(momentum_ranking)} < {self.rotation_count}"
            )
            return signals
        
        # 获取选中的行业
        selected = [item.symbol for item in momentum_ranking[:self.rotation_count]]
        self._current_selection = selected
        
        # 计算目标权重
        target_weights = self._get_allocation_weights(selected)
        
        # 计算总资产价值
        if self._initial_allocation_done:
            total_value = portfolio.total_value(current_prices)
        else:
            total_value = self.initial_investment
        
        # 生成交易信号
        for symbol in self.sector_etfs:
            if symbol not in current_prices:
                continue
            
            price = current_prices[symbol]
            if price <= 0:
                continue
            
            target_weight = target_weights.get(symbol, 0.0)
            target_value = total_value * target_weight
            target_qty = target_value / price if price > 0 else 0
            
            # 当前持仓
            position = portfolio.get_position(symbol)
            current_qty = position.quantity if position else 0.0
            
            # 需要调整的数量
            delta_qty = target_qty - current_qty
            
            if abs(delta_qty) < 0.01:  # 最小交易单位
                continue
            
            action = "buy" if delta_qty > 0 else "sell"
            
            # 查找该行业的动量信息
            momentum_info = next(
                (m for m in momentum_ranking if m.symbol == symbol), None
            )
            
            signals.append(
                Signal(
                    symbol=symbol,
                    action=action,
                    quantity=abs(delta_qty),
                    weight=target_weight,
                    price=price,
                    timestamp=current_date,
                    metadata={
                        "reason": "rotation" if self._initial_allocation_done else "initial_allocation",
                        "target_weight": target_weight,
                        "current_qty": current_qty,
                        "momentum": momentum_info.momentum if momentum_info else None,
                        "momentum_rank": momentum_info.rank if momentum_info else None,
                        "selected": symbol in selected,
                    },
                )
            )
        
        if signals:
            self._last_rebalance = current_date
            self._initial_allocation_done = True
            logger.info(
                f"[{self.name}] {'Initial allocation' if not self._initial_allocation_done else 'Rotated'} "
                f"on {current_date.date()}: selected {selected}"
            )
        
        return signals

    def get_target_weights(self) -> Dict[str, float]:
        """获取当前目标权重配置"""
        if not self._current_selection:
            return {symbol: 0.0 for symbol in self.sector_etfs}
        return self._get_allocation_weights(self._current_selection)

    def get_momentum_ranking(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        获取动量排名

        Args:
            data: 价格数据

        Returns:
            动量排名列表
        """
        ranking = self._select_top_sectors(data)
        return [
            {
                "symbol": item.symbol,
                "momentum": item.momentum,
                "return_pct": item.return_pct,
                "rank": item.rank,
                "name": SECTOR_ETFS.get(item.symbol, {}).get("name", item.symbol),
                "category": SECTOR_ETFS.get(item.symbol, {}).get("category", "unknown"),
            }
            for item in ranking
        ]

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
            "type": "行业轮动策略",
            "sector_count": len(self.sector_etfs),
            "rotation_count": self.rotation_count,
            "lookback_period_months": self.lookback_period,
            "rebalance_frequency": self.rebalance_frequency,
            "sectors": self.sector_etfs,
            "current_selection": self._current_selection,
            **self._metadata,
        }
