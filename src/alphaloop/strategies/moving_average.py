"""
双均线趋势跟踪策略 - Moving Average Crossover Strategy

基于短期和长期移动平均线的交叉来生成买卖信号的经典趋势跟踪策略。
短期均线上穿长期均线（金叉）时买入，下穿（死叉）时卖出。
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


@dataclass
class MACrossoverState:
    """均线交叉策略状态"""
    last_short_ma: Optional[float] = None
    last_long_ma: Optional[float] = None
    position_status: Dict[str, str] = None  # "long", "short", "none"
    
    def __post_init__(self):
        if self.position_status is None:
            self.position_status = {}


class MovingAverageCrossoverStrategy(BaseStrategy):
    """
    双均线趋势跟踪策略

    使用短期和长期移动平均线的交叉作为交易信号。
    - 金叉（短期 > 长期）：买入信号
    - 死叉（短期 < 长期）：卖出信号

    适用于趋势明显的市场，在震荡市可能产生较多假信号。

    Examples:
        >>> strategy = MovingAverageCrossoverStrategy(
        ...     symbols=["VTI", "QQQ"],
        ...     short_window=10,
        ...     long_window=30,
        ... )
        >>> signals = strategy.generate_signals(data, portfolio)

    Attributes:
        symbols: 交易标的列表
        short_window: 短期均线窗口（默认10日）
        long_window: 长期均线窗口（默认30日）
        position_size: 每次交易的资金比例
        initial_investment: 初始投资金额
    
    Strategy Metadata:
        - 策略类型: 趋势跟踪
        - 预期年化收益: 8-15%
        - 风险等级: 中等
        - 最佳市场环境: 趋势明显的牛市/熊市
        - 最差市场环境: 震荡市
    """

    def __init__(
        self,
        symbols: List[str],
        short_window: int = 10,
        long_window: int = 30,
        position_size: float = 1.0,
        initial_investment: float = 100000.0,
        name: str = "ma_crossover",
    ):
        """
        初始化双均线策略

        Args:
            symbols: 资产代码列表
            short_window: 短期移动平均线窗口（默认10）
            long_window: 长期移动平均线窗口（默认30）
            position_size: 仓位比例（0-1，默认全仓）
            initial_investment: 初始投资金额
            name: 策略名称

        Raises:
            ValueError: 当 short_window >= long_window 时
        """
        super().__init__(name=name)
        
        if short_window >= long_window:
            raise ValueError(
                f"short_window ({short_window}) must be less than "
                f"long_window ({long_window})"
            )
        
        self.symbols = [s.upper() for s in symbols]
        self.short_window = short_window
        self.long_window = long_window
        self.position_size = position_size
        self.initial_investment = initial_investment
        
        # 内部状态
        self._state: Dict[str, MACrossoverState] = {}
        self._initialized = False
        
        # 策略元数据
        self._metadata = {
            "description": "双均线趋势跟踪策略",
            "expected_return": "8-15%",
            "risk_level": "中等",
            "best_market": "趋势市场",
            "worst_market": "震荡市",
        }

    def initialize(self, **kwargs) -> None:
        """初始化策略状态"""
        super().initialize(**kwargs)
        self._state = {symbol: MACrossoverState() for symbol in self.symbols}
        self._initialized = True

    def _calculate_ma(self, data: pd.Series, window: int) -> Optional[float]:
        """
        计算移动平均线

        Args:
            data: 价格序列
            window: 移动平均窗口

        Returns:
            移动平均值，数据不足时返回None
        """
        if len(data) < window:
            return None
        return data.tail(window).mean()

    def _detect_crossover(
        self, 
        short_ma: float, 
        long_ma: float,
        state: MACrossoverState,
    ) -> Optional[str]:
        """
        检测均线交叉信号

        Args:
            short_ma: 短期均线值
            long_ma: 长期均线值
            state: 当前状态

        Returns:
            "golden_cross"（金叉）, "death_cross"（死叉）, 或 None
        """
        if state.last_short_ma is None or state.last_long_ma is None:
            # 首次计算，记录状态
            return None
        
        # 当前状态
        current_above = short_ma > long_ma
        last_above = state.last_short_ma > state.last_long_ma
        
        # 金叉：短期从下方穿越到上方
        if current_above and not last_above:
            return "golden_cross"
        
        # 死叉：短期从上方穿越到下方
        if not current_above and last_above:
            return "death_cross"
        
        return None

    def generate_signals(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
        current_date: Optional[datetime] = None,
    ) -> List[Signal]:
        """
        生成交易信号

        根据双均线交叉生成买入/卖出信号。

        Args:
            data: 历史价格数据 (DataFrame with columns = symbols)
            portfolio: 当前投资组合
            current_date: 当前日期

        Returns:
            交易信号列表
        """
        signals = []
        
        if data.empty or len(data) < self.long_window:
            return signals
        
        current_prices = data.iloc[-1].to_dict()
        total_value = portfolio.total_value(current_prices) if portfolio.has_positions else self.initial_investment
        
        for symbol in self.symbols:
            if symbol not in data.columns:
                continue
            
            price_series = data[symbol].dropna()
            if len(price_series) < self.long_window:
                continue
            
            # 计算双均线
            short_ma = self._calculate_ma(price_series, self.short_window)
            long_ma = self._calculate_ma(price_series, self.long_window)
            
            if short_ma is None or long_ma is None:
                continue
            
            state = self._state.get(symbol, MACrossoverState())
            
            # 检测交叉
            crossover = self._detect_crossover(short_ma, long_ma, state)
            
            if crossover:
                current_price = current_prices.get(symbol, 0.0)
                if current_price <= 0:
                    continue
                
                if crossover == "golden_cross":
                    # 金叉 - 买入
                    target_value = total_value * self.position_size / len(self.symbols)
                    quantity = target_value / current_price
                    
                    signals.append(
                        Signal(
                            symbol=symbol,
                            action="buy",
                            quantity=quantity,
                            weight=self.position_size / len(self.symbols),
                            price=current_price,
                            timestamp=current_date,
                            metadata={
                                "reason": "golden_cross",
                                "short_ma": short_ma,
                                "long_ma": long_ma,
                                "strategy": "ma_crossover",
                            },
                        )
                    )
                    logger.info(f"[{self.name}] Golden cross for {symbol} @ {current_price:.2f}")
                    
                elif crossover == "death_cross":
                    # 死叉 - 卖出
                    position = portfolio.get_position(symbol)
                    if position and position.quantity > 0:
                        signals.append(
                            Signal(
                                symbol=symbol,
                                action="sell",
                                quantity=position.quantity,
                                weight=0.0,
                                price=current_price,
                                timestamp=current_date,
                                metadata={
                                    "reason": "death_cross",
                                    "short_ma": short_ma,
                                    "long_ma": long_ma,
                                    "strategy": "ma_crossover",
                                },
                            )
                        )
                        logger.info(f"[{self.name}] Death cross for {symbol} @ {current_price:.2f}")
            
            # 更新状态
            state.last_short_ma = short_ma
            state.last_long_ma = long_ma
            self._state[symbol] = state
        
        return signals

    def get_target_weights(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> Dict[str, float]:
        """
        获取目标权重

        基于当前趋势状态动态调整权重。

        Args:
            data: 价格数据
            portfolio: 当前组合

        Returns:
            目标权重字典
        """
        if data.empty or len(data) < self.long_window:
            return {s: 0.0 for s in self.symbols}
        
        weights = {}
        for symbol in self.symbols:
            if symbol not in data.columns:
                weights[symbol] = 0.0
                continue
            
            price_series = data[symbol].dropna()
            if len(price_series) < self.long_window:
                weights[symbol] = 0.0
                continue
            
            short_ma = self._calculate_ma(price_series, self.short_window)
            long_ma = self._calculate_ma(price_series, self.long_window)
            
            # 短期 > 长期时持有多头，否则空仓
            if short_ma and long_ma and short_ma > long_ma:
                weights[symbol] = self.position_size / len(self.symbols)
            else:
                weights[symbol] = 0.0
        
        return weights

    def get_summary(self) -> Dict[str, Any]:
        """获取策略摘要"""
        return {
            "name": self.name,
            "type": "双均线趋势跟踪",
            "short_window": self.short_window,
            "long_window": self.long_window,
            "position_size": self.position_size,
            "symbols": self.symbols,
            **self._metadata,
        }
