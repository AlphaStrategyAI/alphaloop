"""
风险平价策略 - Risk Parity Strategy

各资产风险贡献相等，而非资金相等。
通过波动率倒数作为权重基础，实现各资产对组合风险的贡献相同。
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..core.portfolio import Portfolio
from .base import BaseStrategy, Signal

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """风险指标"""
    volatility: float
    weight: float
    risk_contribution: float


class RiskParityStrategy(BaseStrategy):
    """
    风险平价策略

    风险平价的核心思想是使组合中各资产对总风险的贡献相等，
    而非传统的资金权重相等。

    策略逻辑：
    1. 计算各资产的历史波动率（风险）
    2. 使用波动率倒数作为权重基础
    3. 权重调整后可实现各资产风险贡献相等
    4. 可设置目标波动率和最大杠杆

    优势：
    - 风险分散更均衡
    - 低波动资产自动获得更高权重
    - 适合多资产配置

    Examples:
        >>> # 基础用法
        >>> strategy = RiskParityStrategy(
        ...     symbols=["VTI", "BND", "GLD", "VNQ"],
        ...     target_volatility=0.10,  # 10%目标波动率
        ... )
        
        >>> # 带杠杆限制
        >>> strategy = RiskParityStrategy(
        ...     symbols=["VTI", "BND", "GLD"],
        ...     target_volatility=0.08,
        ...     max_leverage=1.5,
        ...     risk_lookback=60,  # 60天风险回看
        ... )

    Attributes:
        symbols: 资产代码列表
        target_volatility: 目标年化波动率（5-15%，默认10%）
        max_leverage: 最大杠杆倍数（1-2，默认1.0）
        risk_lookback: 风险计算回看天数（30-90，默认60）
        rebalance_frequency: 再平衡频率（"monthly"/"quarterly"）
        initial_investment: 初始投资金额
    
    Strategy Metadata:
        - 策略类型: 风险平价 / 资产配置
        - 预期年化收益: 6-10%
        - 风险等级: 中低（风险分散均衡）
        - 最佳适用: 多资产组合、风险敏感型投资者
        - 理论基础: 桥水基金All Weather策略、风险预算
    """

    def __init__(
        self,
        symbols: List[str],
        target_volatility: float = 0.10,
        max_leverage: float = 1.0,
        risk_lookback: int = 60,
        rebalance_frequency: str = "monthly",
        initial_investment: float = 100000.0,
        name: str = "risk_parity",
    ):
        """
        初始化风险平价策略

        Args:
            symbols: 资产代码列表（至少2个）
            target_volatility: 目标年化波动率（0.05-0.15，默认0.10）
            max_leverage: 最大杠杆倍数（1.0-2.0，默认1.0）
            risk_lookback: 风险计算回看天数（30-90，默认60）
            rebalance_frequency: 再平衡频率（"monthly"/"quarterly"）
            initial_investment: 初始投资金额
            name: 策略名称

        Raises:
            ValueError: 参数不合法时
        """
        super().__init__(name=name)
        
        if len(symbols) < 2:
            raise ValueError(f"At least 2 symbols required, got {len(symbols)}")
        
        if not 0.05 <= target_volatility <= 0.15:
            raise ValueError(
                f"target_volatility must be between 5% and 15%, "
                f"got {target_volatility:.1%}"
            )
        
        if not 1.0 <= max_leverage <= 2.0:
            raise ValueError(
                f"max_leverage must be between 1.0 and 2.0, got {max_leverage}"
            )
        
        if not 30 <= risk_lookback <= 90:
            raise ValueError(
                f"risk_lookback must be between 30 and 90 days, got {risk_lookback}"
            )
        
        self.symbols = [s.upper() for s in symbols]
        self.target_volatility = target_volatility
        self.max_leverage = max_leverage
        self.risk_lookback = risk_lookback
        self.rebalance_frequency = rebalance_frequency.lower()
        self.initial_investment = initial_investment
        
        # 内部状态
        self._last_rebalance: Optional[datetime] = None
        self._initial_allocation_done = False
        self._current_weights: Dict[str, float] = {}
        
        # 再平衡间隔天数
        self._frequency_days = {
            "monthly": 30,
            "quarterly": 91,
        }.get(self.rebalance_frequency, 30)
        
        # 策略元数据
        self._metadata = {
            "description": "风险平价策略 - 各资产风险贡献相等",
            "expected_return": "6-10%",
            "risk_level": "中低",
            "best_for": "多资产组合、风险敏感型投资者",
            "theoretical_basis": "桥水All Weather策略、风险预算",
        }
        
        logger.info(
            f"Initialized {self.name}: {len(symbols)} assets, "
            f"{target_volatility:.1%} target vol, {max_leverage}x max leverage"
        )

    def initialize(self, **kwargs) -> None:
        """初始化策略"""
        super().initialize(**kwargs)
        self._last_rebalance = None
        self._initial_allocation_done = False
        self._current_weights = {}

    @property
    def asset_symbols(self) -> List[str]:
        """获取资产代码列表"""
        return self.symbols.copy()

    def _calculate_volatility(self, data: pd.DataFrame, symbol: str) -> Optional[float]:
        """
        计算资产波动率

        Args:
            data: 历史价格数据
            symbol: 资产代码

        Returns:
            年化波动率，数据不足时返回None
        """
        if symbol not in data.columns:
            return None
        
        price_series = data[symbol].dropna()
        
        if len(price_series) < self.risk_lookback + 1:
            return None
        
        # 计算日收益率
        returns = price_series.pct_change().dropna()
        
        if len(returns) < self.risk_lookback:
            return None
        
        # 取最近risk_lookback天的收益率
        recent_returns = returns.tail(self.risk_lookback)
        
        # 计算日波动率并年化（假设252个交易日/年）
        daily_vol = recent_returns.std()
        annual_vol = daily_vol * np.sqrt(252)
        
        return annual_vol

    def _calculate_risk_parity_weights(
        self, data: pd.DataFrame
    ) -> Dict[str, float]:
        """
        计算风险平价权重

        使用波动率倒数作为权重基础：
        weight_i = (1/vol_i) / sum(1/vol_j)

        Args:
            data: 历史价格数据

        Returns:
            风险平价权重字典
        """
        volatilities = {}
        
        # 计算各资产波动率
        for symbol in self.symbols:
            vol = self._calculate_volatility(data, symbol)
            if vol is not None and vol > 0:
                volatilities[symbol] = vol
        
        if not volatilities:
            return {symbol: 0.0 for symbol in self.symbols}
        
        # 计算波动率倒数
        inverse_vols = {s: 1.0 / v for s, v in volatilities.items()}
        
        # 归一化得到权重
        total_inverse_vol = sum(inverse_vols.values())
        
        if total_inverse_vol <= 0:
            return {symbol: 0.0 for symbol in self.symbols}
        
        weights = {s: iv / total_inverse_vol for s, iv in inverse_vols.items()}
        
        # 未计算到波动率的资产权重设为0
        for symbol in self.symbols:
            if symbol not in weights:
                weights[symbol] = 0.0
        
        return weights

    def _apply_leverage_and_target_vol(
        self, weights: Dict[str, float], portfolio_vol: Optional[float] = None
    ) -> Dict[str, float]:
        """
        应用杠杆和目标波动率调整

        Args:
            weights: 基础权重
            portfolio_vol: 当前组合波动率（用于缩放）

        Returns:
            调整后的权重
        """
        # 基础权重和
        total_weight = sum(weights.values())
        
        if total_weight <= 0:
            return weights
        
        # 归一化
        normalized_weights = {s: w / total_weight for s, w in weights.items()}
        
        # 应用杠杆
        if portfolio_vol is not None and portfolio_vol > 0:
            # 根据目标波动率调整杠杆
            leverage = min(self.target_volatility / portfolio_vol, self.max_leverage)
        else:
            leverage = 1.0
        
        leverage = max(1.0, min(leverage, self.max_leverage))
        
        adjusted_weights = {s: w * leverage for s, w in normalized_weights.items()}
        
        return adjusted_weights

    def _calculate_portfolio_volatility(
        self, data: pd.DataFrame, weights: Dict[str, float]
    ) -> Optional[float]:
        """
        计算组合波动率

        Args:
            data: 历史价格数据
            weights: 资产权重

        Returns:
            组合年化波动率
        """
        # 计算收益率矩阵
        returns_data = pd.DataFrame()
        for symbol in self.symbols:
            if symbol in data.columns:
                returns_data[symbol] = data[symbol].pct_change()
        
        if returns_data.empty:
            return None
        
        # 取最近risk_lookback天的数据
        recent_returns = returns_data.tail(self.risk_lookback).dropna()
        
        if len(recent_returns) < self.risk_lookback // 2:
            return None
        
        # 构建权重向量
        weight_vector = np.array([weights.get(s, 0.0) for s in recent_returns.columns])
        
        # 计算协方差矩阵
        cov_matrix = recent_returns.cov().values
        
        # 计算组合方差: w^T * Σ * w
        portfolio_variance = weight_vector.T @ cov_matrix @ weight_vector
        
        # 年化波动率
        portfolio_vol = np.sqrt(portfolio_variance) * np.sqrt(252)
        
        return portfolio_vol

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
        2. 计算各资产波动率
        3. 基于波动率倒数计算风险平价权重
        4. 应用目标波动率和杠杆限制
        5. 生成再平衡信号

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
        
        # 计算风险平价权重
        rp_weights = self._calculate_risk_parity_weights(data)
        
        # 计算当前组合波动率（如果已持仓）
        current_portfolio_vol = None
        if self._initial_allocation_done and self._current_weights:
            current_portfolio_vol = self._calculate_portfolio_volatility(
                data, self._current_weights
            )
        
        # 应用杠杆和目标波动率调整
        final_weights = self._apply_leverage_and_target_vol(
            rp_weights, current_portfolio_vol
        )
        
        self._current_weights = final_weights
        
        # 计算总资产价值
        if self._initial_allocation_done:
            total_value = portfolio.total_value(current_prices)
        else:
            total_value = self.initial_investment
        
        # 生成交易信号
        for symbol in self.symbols:
            if symbol not in current_prices:
                continue
            
            price = current_prices[symbol]
            if price <= 0:
                continue
            
            target_weight = final_weights.get(symbol, 0.0)
            target_value = total_value * target_weight
            target_qty = target_value / price if price > 0 else 0
            
            # 当前持仓
            position = portfolio.get_position(symbol)
            current_qty = position.quantity if position else 0.0
            
            # 需要调整的数量
            delta_qty = target_qty - current_qty
            
            # 最小交易阈值（100美元价值）
            if abs(delta_qty) * price < 100:
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
                        "reason": "risk_parity_rebalance" if self._initial_allocation_done else "initial_allocation",
                        "target_weight": target_weight,
                        "volatility": self._calculate_volatility(data, symbol),
                        "risk_contribution": target_weight / len(self.symbols),  # 简化的风险贡献
                    },
                )
            )
        
        if signals:
            self._last_rebalance = current_date
            self._initial_allocation_done = True
            logger.info(
                f"[{self.name}] {'Initial allocation' if not self._initial_allocation_done else 'Rebalanced'} "
                f"on {current_date.date()}: target vol={self.target_volatility:.1%}"
            )
        
        return signals

    def get_target_weights(self) -> Dict[str, float]:
        """获取当前目标权重配置"""
        return self._current_weights.copy()

    def get_risk_metrics(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        获取风险指标

        Args:
            data: 价格数据

        Returns:
            风险指标字典
        """
        metrics = {}
        total_risk = 0.0
        
        for symbol in self.symbols:
            vol = self._calculate_volatility(data, symbol)
            weight = self._current_weights.get(symbol, 0.0)
            risk_contribution = weight * vol if vol else 0.0
            total_risk += risk_contribution
            
            metrics[symbol] = {
                "volatility": vol if vol else None,
                "weight": weight,
                "risk_contribution": risk_contribution,
            }
        
        # 计算风险贡献占比（应该是相等的）
        if total_risk > 0:
            for symbol in metrics:
                metrics[symbol]["risk_contribution_pct"] = (
                    metrics[symbol]["risk_contribution"] / total_risk
                )
        
        # 组合波动率
        portfolio_vol = self._calculate_portfolio_volatility(data, self._current_weights)
        
        return {
            "assets": metrics,
            "portfolio_volatility": portfolio_vol,
            "target_volatility": self.target_volatility,
            "total_weight": sum(self._current_weights.values()),
        }

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
            "type": "风险平价策略",
            "asset_count": len(self.symbols),
            "target_volatility": f"{self.target_volatility:.1%}",
            "max_leverage": f"{self.max_leverage}x",
            "risk_lookback_days": self.risk_lookback,
            "rebalance_frequency": self.rebalance_frequency,
            "symbols": self.symbols,
            "current_weights": self._current_weights,
            **self._metadata,
        }
