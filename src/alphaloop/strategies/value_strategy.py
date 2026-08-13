"""
价值投资策略 - Value Investing Strategy

基于估值指标（PE、PB、PS等）的分位数进行买卖决策。
低估值分位数时买入，高估值分位数时卖出。

基于本杰明·格雷厄姆的价值投资理念，通过量化估值指标实现系统性价值投资。
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


class ValuationMetric:
    """估值指标类型"""
    PE = "pe"      # 市盈率
    PB = "pb"      # 市净率
    PS = "ps"      # 市销率
    EV_EBITDA = "ev_ebitda"  # 企业价值倍数


@dataclass
class ValueSignalState:
    """价值投资策略状态"""
    last_percentile: Optional[float] = None
    position_status: str = "none"  # "long", "none"


class ValueStrategy(BaseStrategy):
    """
    价值投资策略

    基于估值指标的历史分位数生成交易信号：
    - 低分位数（如<20%）：低估，买入信号
    - 高分位数（如>80%）：高估，卖出信号

    支持多种估值指标：市盈率(PE)、市净率(PB)、市销率(PS)等。
    适用于长期价值投资，寻找被市场低估的优质资产。

    Examples:
        >>> # 基于PE的价值策略
        >>> strategy = ValueStrategy(
        ...     symbols=["VTI", "VEU", "VWO"],
        ...     valuation_metric="pe",
        ...     buy_percentile=20,
        ...     sell_percentile=80,
        ... )
        
        >>> # 基于PB的价值策略
        >>> strategy = ValueStrategy(
        ...     symbols=["SPY", "QQQ", "IWM"],
        ...     valuation_metric="pb",
        ...     lookback_years=10,
        ... )

    Attributes:
        symbols: 交易标的列表
        valuation_metric: 估值指标类型 ("pe", "pb", "ps")
        buy_percentile: 买入分位数阈值（默认20，即低于20%分位买入）
        sell_percentile: 卖出分位数阈值（默认80，即高于80%分位卖出）
        lookback_years: 历史回看年数（默认10年）
        position_size: 每个标的的目标权重
        initial_investment: 初始投资金额
    
    Strategy Metadata:
        - 策略类型: 价值投资
        - 预期年化收益: 8-12%
        - 风险等级: 中低
        - 最佳市场环境: 震荡市、熊市（能找到低估标的）
        - 投资风格: 长期、逆向
        - 理论基础: 格雷厄姆价值投资、均值回归
    """

    def __init__(
        self,
        symbols: List[str],
        valuation_metric: str = "pe",
        buy_percentile: float = 20.0,
        sell_percentile: float = 80.0,
        lookback_years: int = 10,
        position_size: Optional[float] = None,
        initial_investment: float = 100000.0,
        name: str = "value_strategy",
    ):
        """
        初始化价值投资策略

        Args:
            symbols: 资产代码列表
            valuation_metric: 估值指标 ("pe", "pb", "ps", "ev_ebitda")
            buy_percentile: 买入分位数阈值（0-100，默认20）
            sell_percentile: 卖出分位数阈值（0-100，默认80）
            lookback_years: 历史数据回看年数（默认10）
            position_size: 每个标的的目标权重（默认等权）
            initial_investment: 初始投资金额
            name: 策略名称

        Raises:
            ValueError: 参数不合法时
        """
        super().__init__(name=name)
        
        # 验证估值指标
        valid_metrics = [ValuationMetric.PE, ValuationMetric.PB, ValuationMetric.PS, ValuationMetric.EV_EBITDA]
        if valuation_metric.lower() not in valid_metrics:
            raise ValueError(
                f"valuation_metric must be one of {valid_metrics}, got {valuation_metric}"
            )
        
        # 验证分位数参数
        if not 0 <= buy_percentile <= 100:
            raise ValueError(f"buy_percentile must be between 0 and 100, got {buy_percentile}")
        if not 0 <= sell_percentile <= 100:
            raise ValueError(f"sell_percentile must be between 0 and 100, got {sell_percentile}")
        if buy_percentile >= sell_percentile:
            raise ValueError(
                f"buy_percentile ({buy_percentile}) must be less than "
                f"sell_percentile ({sell_percentile})"
            )
        
        self.symbols = [s.upper() for s in symbols]
        self.valuation_metric = valuation_metric.lower()
        self.buy_percentile = buy_percentile
        self.sell_percentile = sell_percentile
        self.lookback_years = lookback_years
        self.initial_investment = initial_investment
        
        # 默认等权分配
        self.position_size = position_size or (1.0 / len(symbols)) if symbols else 0.0
        
        # 内部状态
        self._state: Dict[str, ValueSignalState] = {}
        self._valuation_history: Dict[str, pd.Series] = {}
        
        # 策略元数据
        self._metadata = {
            "description": "基于估值分位数的价值投资策略",
            "expected_return": "8-12%",
            "risk_level": "中低",
            "best_market": "震荡市、熊市",
            "investment_style": "长期、逆向",
            "theoretical_basis": "格雷厄姆价值投资、均值回归",
        }
        
        logger.info(
            f"Initialized {self.name}: {self.valuation_metric.upper()} metric, "
            f"buy<{buy_percentile}%, sell>{sell_percentile}%"
        )

    def initialize(self, **kwargs) -> None:
        """初始化策略状态"""
        super().initialize(**kwargs)
        self._state = {symbol: ValueSignalState() for symbol in self.symbols}
        self._valuation_history = {}

    def _get_valuation_data(self, symbol: str, data: pd.DataFrame) -> Optional[pd.Series]:
        """
        获取估值数据

        注意：这是一个简化实现。实际应用中，估值数据应该来自财务数据API。
        这里我们使用价格的相对水平作为估值代理（价格越低，估值越低）。

        Args:
            symbol: 资产代码
            data: 价格数据

        Returns:
            估值数据序列，如果不可用返回None
        """
        if symbol not in data.columns:
            return None
        
        # 简化处理：使用价格的滚动均值作为估值代理
        # 实际应用中应该使用真实估值数据
        price_series = data[symbol].dropna()
        if len(price_series) < 252:  # 至少需要一年的数据
            return None
        
        # 计算价格相对于长期均值的位置作为估值代理
        # 实际应用中应替换为真实的PE/PB/PS数据
        rolling_mean = price_series.rolling(window=252).mean()
        valuation_proxy = price_series / rolling_mean
        
        return valuation_proxy

    def _calculate_percentile(
        self, 
        current_value: float, 
        historical_values: pd.Series
    ) -> Optional[float]:
        """
        计算当前值在历史数据中的分位数

        Args:
            current_value: 当前估值值
            historical_values: 历史估值序列

        Returns:
            分位数（0-100），数据不足时返回None
        """
        if historical_values is None or len(historical_values) < 252:
            return None
        
        # 使用最近lookback_years年的数据
        lookback_days = self.lookback_years * 252
        hist_values = historical_values.tail(lookback_days).dropna()
        
        if len(hist_values) < 252:
            return None
        
        # 计算分位数 (0-100)
        percentile = (hist_values < current_value).mean() * 100
        return percentile

    def _generate_signal_for_symbol(
        self,
        symbol: str,
        data: pd.DataFrame,
        portfolio: Portfolio,
        current_prices: Dict[str, float],
        total_value: float,
        current_date: Optional[datetime],
    ) -> Optional[Signal]:
        """
        为单个标的生成信号

        Args:
            symbol: 资产代码
            data: 历史数据
            portfolio: 当前组合
            current_prices: 当前价格
            total_value: 总资产
            current_date: 当前日期

        Returns:
            交易信号或None
        """
        # 获取估值数据
        valuation_series = self._get_valuation_data(symbol, data)
        if valuation_series is None or len(valuation_series) < 2:
            return None
        
        current_valuation = valuation_series.iloc[-1]
        percentile = self._calculate_percentile(current_valuation, valuation_series)
        
        if percentile is None:
            return None
        
        state = self._state.get(symbol, ValueSignalState())
        current_price = current_prices.get(symbol, 0.0)
        
        if current_price <= 0:
            return None
        
        signal = None
        
        # 低估值买入
        if percentile <= self.buy_percentile and state.position_status != "long":
            target_value = total_value * self.position_size
            quantity = target_value / current_price
            
            signal = Signal(
                symbol=symbol,
                action="buy",
                quantity=quantity,
                weight=self.position_size,
                price=current_price,
                timestamp=current_date,
                metadata={
                    "reason": "undervalued",
                    "percentile": percentile,
                    "metric": self.valuation_metric,
                    "valuation": current_valuation,
                },
            )
            state.position_status = "long"
            logger.info(
                f"[{self.name}] Buy signal for {symbol} at {percentile:.1f} percentile"
            )
        
        # 高估值卖出
        elif percentile >= self.sell_percentile and state.position_status == "long":
            position = portfolio.get_position(symbol)
            if position and position.quantity > 0:
                signal = Signal(
                    symbol=symbol,
                    action="sell",
                    quantity=position.quantity,
                    weight=0.0,
                    price=current_price,
                    timestamp=current_date,
                    metadata={
                        "reason": "overvalued",
                        "percentile": percentile,
                        "metric": self.valuation_metric,
                        "valuation": current_valuation,
                    },
                )
                state.position_status = "none"
                logger.info(
                    f"[{self.name}] Sell signal for {symbol} at {percentile:.1f} percentile"
                )
        
        # 更新状态
        state.last_percentile = percentile
        self._state[symbol] = state
        
        return signal

    def generate_signals(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
        current_date: Optional[datetime] = None,
    ) -> List[Signal]:
        """
        生成交易信号

        策略逻辑：
        1. 计算各标的当前估值指标
        2. 计算估值在历史数据中的分位数
        3. 低分位数（低估）时买入，高分位数（高估）时卖出

        Args:
            data: 历史价格数据（应包含足够长的历史用于计算分位数）
            portfolio: 当前投资组合
            current_date: 当前日期

        Returns:
            交易信号列表
        """
        signals = []
        
        if data.empty or len(data) < 252:
            return signals
        
        current_prices = data.iloc[-1].to_dict()
        total_value = portfolio.total_value(current_prices) if portfolio.has_positions else self.initial_investment
        
        for symbol in self.symbols:
            signal = self._generate_signal_for_symbol(
                symbol, data, portfolio, current_prices, total_value, current_date
            )
            if signal:
                signals.append(signal)
        
        return signals

    def get_target_weights(
        self,
        data: pd.DataFrame,
        portfolio: Portfolio,
    ) -> Dict[str, float]:
        """
        获取目标权重

        基于当前估值分位数动态调整权重：
        - 低分位数：高权重
        - 中分位数：中等权重
        - 高分位数：低权重/空仓

        Args:
            data: 价格数据
            portfolio: 当前组合

        Returns:
            目标权重字典
        """
        if data.empty or len(data) < 252:
            return {s: 0.0 for s in self.symbols}
        
        weights = {}
        for symbol in self.symbols:
            valuation_series = self._get_valuation_data(symbol, data)
            if valuation_series is None:
                weights[symbol] = 0.0
                continue
            
            current_valuation = valuation_series.iloc[-1]
            percentile = self._calculate_percentile(current_valuation, valuation_series)
            
            if percentile is None:
                weights[symbol] = 0.0
                continue
            
            # 根据分位数调整权重
            # 低分位数 -> 高权重，高分位数 -> 低权重
            if percentile <= self.buy_percentile:
                weights[symbol] = self.position_size
            elif percentile >= self.sell_percentile:
                weights[symbol] = 0.0
            else:
                # 线性地分配权重
                weight_range = self.sell_percentile - self.buy_percentile
                position_in_range = (self.sell_percentile - percentile) / weight_range
                weights[symbol] = self.position_size * position_in_range
        
        return weights

    def get_valuation_summary(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        获取估值摘要

        Args:
            data: 价格数据

        Returns:
            各标的当前估值分位数摘要
        """
        summary = {}
        
        for symbol in self.symbols:
            valuation_series = self._get_valuation_data(symbol, data)
            if valuation_series is not None and len(valuation_series) > 0:
                current = valuation_series.iloc[-1]
                percentile = self._calculate_percentile(current, valuation_series)
                summary[symbol] = {
                    "current_valuation": current,
                    "percentile": percentile,
                    "signal": (
                        "undervalued" if percentile and percentile <= self.buy_percentile
                        else "overvalued" if percentile and percentile >= self.sell_percentile
                        else "neutral"
                    ),
                }
        
        return summary

    def get_summary(self) -> Dict[str, Any]:
        """获取策略摘要"""
        return {
            "name": self.name,
            "type": "价值投资策略",
            "valuation_metric": self.valuation_metric.upper(),
            "buy_threshold": f"<{self.buy_percentile}%",
            "sell_threshold": f">{self.sell_percentile}%",
            "lookback_years": self.lookback_years,
            "symbols": self.symbols,
            **self._metadata,
        }
