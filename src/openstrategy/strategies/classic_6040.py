"""
经典60/40配置策略 - Classic 60/40 Portfolio Strategy

经典的资产配置策略，60%股票 + 40%债券。
这是投资界最著名的配置策略之一，平衡了增长和稳定性。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from ..core.portfolio import Portfolio
from .base import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class Classic6040Strategy(BaseStrategy):
    """
    经典60/40配置策略

    将资金配置为60%股票和40%债券的经典组合。
    定期再平衡以维持目标配置比例。

    这是投资界最经典的资产配置策略，由诺贝尔经济学奖得主哈里·马科维茨的
    现代投资组合理论支持，被广泛用于养老金、捐赠基金等长期投资者。

    Examples:
        >>> strategy = Classic6040Strategy(
        ...     equity_symbol="VTI",  # 全股票市场ETF
        ...     bond_symbol="BND",    # 全债券市场ETF
        ...     rebalance_frequency="yearly",
        ... )
        >>> signals = strategy.generate_signals(data, portfolio)

        >>> # 自定义比例
        >>> strategy = Classic6040Strategy(
        ...     equity_symbol="SPY",
        ...     bond_symbol="TLT",
        ...     equity_ratio=0.7,  # 70%股票
        ...     rebalance_frequency="quarterly",
        ... )

    Attributes:
        equity_symbol: 股票ETF代码
        bond_symbol: 债券ETF代码
        equity_ratio: 股票配置比例（默认0.6）
        bond_ratio: 债券配置比例（自动计算为1 - equity_ratio）
        rebalance_frequency: 再平衡频率
        initial_investment: 初始投资金额
        tolerance: 最小交易阈值
    
    Strategy Metadata:
        - 策略类型: 资产配置
        - 预期年化收益: 6-10%
        - 风险等级: 中低
        - 最佳适用: 长期投资者、退休规划
        - 历史表现: 过去50年年化回报约8-9%
    """

    # 常用ETF推荐
    RECOMMENDED_ETFS = {
        "equity": {
            "VTI": "Vanguard Total Stock Market ETF (美股全市场)",
            "SPY": "SPDR S&P 500 ETF (标普500)",
            "VEU": "Vanguard FTSE All-World ex-US ETF (国际股票)",
            "VT": "Vanguard Total World Stock ETF (全球股票)",
        },
        "bond": {
            "BND": "Vanguard Total Bond Market ETF (美债全市场)",
            "AGG": "iShares Core U.S. Aggregate Bond ETF (美债综合)",
            "TLT": "iShares 20+ Year Treasury Bond ETF (长期美债)",
            "BNDW": "Vanguard Total World Bond ETF (全球债券)",
        },
    }

    def __init__(
        self,
        equity_symbol: str = "VTI",
        bond_symbol: str = "BND",
        equity_ratio: float = 0.6,
        rebalance_frequency: str = "yearly",
        initial_investment: float = 100000.0,
        tolerance: float = 0.001,
        name: str = "classic_6040",
    ):
        """
        初始化60/40配置策略

        Args:
            equity_symbol: 股票ETF代码（默认VTI）
            bond_symbol: 债券ETF代码（默认BND）
            equity_ratio: 股票配置比例（0-1，默认0.6）
            rebalance_frequency: 再平衡频率
                - "monthly": 每月
                - "quarterly": 每季度
                - "yearly": 每年（默认）
            initial_investment: 初始投资金额
            tolerance: 最小交易阈值（占总资产比例）
            name: 策略名称

        Raises:
            ValueError: 当 equity_ratio 不在 (0, 1) 范围内时
        """
        super().__init__(name=name)
        
        if not 0 < equity_ratio < 1:
            raise ValueError(f"equity_ratio must be between 0 and 1, got {equity_ratio}")
        
        self.equity_symbol = equity_symbol.upper()
        self.bond_symbol = bond_symbol.upper()
        self.equity_ratio = equity_ratio
        self.bond_ratio = 1.0 - equity_ratio
        self.rebalance_frequency = rebalance_frequency.lower()
        self.initial_investment = initial_investment
        self.tolerance = tolerance
        
        # 内部状态
        self._last_rebalance: Optional[datetime] = None
        self._initial_allocation_done = False
        
        # 再平衡间隔天数
        self._frequency_days = {
            "monthly": 30,
            "quarterly": 91,
            "yearly": 365,
        }.get(self.rebalance_frequency, 365)
        
        # 策略元数据
        self._metadata = {
            "description": "经典60/40股债配置策略",
            "expected_return": "6-10%",
            "risk_level": "中低",
            "best_for": "长期投资者、退休规划",
            "historical_return": "8-9% (50年历史)",
        }
        
        logger.info(
            f"Initialized {self.name}: {self.equity_ratio:.0%} {self.equity_symbol} + "
            f"{self.bond_ratio:.0%} {self.bond_symbol}, rebalancing {rebalance_frequency}"
        )

    def initialize(self, **kwargs) -> None:
        """初始化策略"""
        super().initialize(**kwargs)
        self._last_rebalance = None
        self._initial_allocation_done = False

    @property
    def symbols(self) -> List[str]:
        """获取策略使用的所有资产代码"""
        return [self.equity_symbol, self.bond_symbol]

    def get_target_weights(self) -> Dict[str, float]:
        """获取目标权重配置"""
        return {
            self.equity_symbol: self.equity_ratio,
            self.bond_symbol: self.bond_ratio,
        }

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

    def _calculate_deviation(
        self, 
        portfolio: Portfolio, 
        prices: Dict[str, float]
    ) -> float:
        """
        计算当前配置偏离度

        Args:
            portfolio: 当前组合
            prices: 当前价格

        Returns:
            最大偏离值
        """
        total_value = portfolio.total_value(prices)
        if total_value <= 0:
            return 0.0
        
        target_weights = self.get_target_weights()
        max_deviation = 0.0
        
        for symbol, target_weight in target_weights.items():
            position = portfolio.get_position(symbol)
            current_value = (position.quantity * prices.get(symbol, 0)) if position else 0
            current_weight = current_value / total_value
            deviation = abs(current_weight - target_weight)
            max_deviation = max(max_deviation, deviation)
        
        return max_deviation

    def _generate_allocation_signals(
        self,
        prices: Dict[str, float],
        current_date: datetime,
        total_value: float,
    ) -> List[Signal]:
        """
        生成配置/再平衡信号

        Args:
            prices: 当前价格
            current_date: 当前日期
            total_value: 总资产价值

        Returns:
            交易信号列表
        """
        signals = []
        target_weights = self.get_target_weights()
        
        for symbol, target_weight in target_weights.items():
            if symbol not in prices:
                logger.warning(f"Price not available for {symbol}")
                continue
            
            price = prices[symbol]
            if price <= 0:
                continue
            
            target_value = total_value * target_weight
            target_quantity = target_value / price
            
            signals.append(
                Signal(
                    symbol=symbol,
                    action="buy",
                    quantity=target_quantity,
                    weight=target_weight,
                    price=price,
                    timestamp=current_date,
                    metadata={
                        "reason": "initial_allocation" if not self._initial_allocation_done else "rebalance",
                        "target_weight": target_weight,
                        "total_value": total_value,
                    },
                )
            )
        
        return signals

    def generate_signals(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
        current_date: Optional[datetime] = None,
    ) -> List[Signal]:
        """
        生成交易信号

        策略逻辑：
        1. 初始配置：按60/40比例买入股票和债券
        2. 定期再平衡：按设定频率恢复目标配置

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
        
        current_prices = data.iloc[-1].to_dict()
        
        # 初始配置
        if not self._initial_allocation_done:
            signals = self._generate_allocation_signals(
                current_prices, current_date, self.initial_investment
            )
            self._initial_allocation_done = True
            self._last_rebalance = current_date
            logger.info(f"[{self.name}] Initial allocation on {current_date.date()}")
            return signals
        
        # 检查是否需要再平衡
        if not self._should_rebalance(current_date):
            return signals
        
        # 执行再平衡
        total_value = portfolio.total_value(current_prices)
        target_weights = self.get_target_weights()
        
        for symbol, target_weight in target_weights.items():
            if symbol not in current_prices:
                continue
            
            price = current_prices[symbol]
            if price <= 0:
                continue
            
            # 当前持仓
            position = portfolio.get_position(symbol)
            current_qty = position.quantity if position else 0.0
            current_value = current_qty * price
            current_weight = current_value / total_value if total_value > 0 else 0
            
            # 目标持仓
            target_value = total_value * target_weight
            target_qty = target_value / price
            
            # 需要调整的数量
            delta_qty = target_qty - current_qty
            delta_value = abs(delta_qty) * price
            
            # 检查最小交易阈值
            if delta_value < self.tolerance * total_value:
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
                        "reason": "rebalance",
                        "current_weight": current_weight,
                        "target_weight": target_weight,
                        "deviation": current_weight - target_weight,
                    },
                )
            )
        
        if signals:
            self._last_rebalance = current_date
            logger.info(
                f"[{self.name}] Rebalanced on {current_date.date()}: "
                f"{len(signals)} trades"
            )
        
        return signals

    def should_rebalance(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
        current_date: datetime,
        last_rebalance: Optional[datetime] = None,
    ) -> bool:
        """
        判断是否需要再平衡（覆盖基类方法）

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
            "type": "经典60/40配置",
            "allocation": {
                self.equity_symbol: f"{self.equity_ratio:.0%}",
                self.bond_symbol: f"{self.bond_ratio:.0%}",
            },
            "rebalance_frequency": self.rebalance_frequency,
            "symbols": self.symbols,
            **self._metadata,
        }
