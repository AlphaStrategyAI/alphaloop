"""
回测引擎 - 执行策略回测的核心组件
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

import pandas as pd

from ..core.asset import Asset
from ..core.portfolio import Portfolio
from ..strategies.base import BaseStrategy, Signal
from .broker import SimulatedBroker
from .metrics import PerformanceMetrics, calculate_metrics

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """回测配置"""

    initial_cash: float = 100000.0
    commission_rate: float = 0.001  # 0.1%
    slippage: float = 0.0  # 滑点
    allow_fractional: bool = True  # 允许小数股
    rebalance_on_start: bool = True


@dataclass
class BacktestResult:
    """回测结果"""

    config: BacktestConfig
    portfolio: Portfolio
    history: pd.DataFrame
    trades: pd.DataFrame
    metrics: PerformanceMetrics

    def summary(self) -> dict:
        """结果摘要"""
        return {
            "total_return": f"{self.metrics.total_return:.2%}",
            "cagr": f"{self.metrics.cagr:.2%}",
            "sharpe_ratio": f"{self.metrics.sharpe_ratio:.2f}",
            "max_drawdown": f"{self.metrics.max_drawdown:.2%}",
            "volatility": f"{self.metrics.volatility:.2%}",
            "n_trades": len(self.trades),
            "final_value": f"${self.portfolio.cash + sum(self.history['total_value'].iloc[-1:]):,.2f}",
        }


class BacktestEngine:
    """
    回测引擎

    执行策略回测的核心组件，管理整个回测流程。

    Examples:
        >>> engine = BacktestEngine(config)
        >>> result = engine.run(strategy, data)
        >>> print(result.metrics.sharpe_ratio)
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        """
        初始化回测引擎

        Args:
            config: 回测配置
        """
        self.config = config or BacktestConfig()
        self.broker = SimulatedBroker(
            commission_rate=self.config.commission_rate,
            slippage=self.config.slippage,
        )
        self._callbacks: List[Callable] = []

    def add_callback(self, callback: Callable) -> None:
        """添加回测过程中的回调函数"""
        self._callbacks.append(callback)

    def run(
        self,
        strategy: BaseStrategy,
        data: pd.DataFrame,
    ) -> BacktestResult:
        """
        运行回测

        Args:
            strategy: 投资策略
            data: 价格数据 (DataFrame with datetime index, columns = symbols)

        Returns:
            回测结果
        """
        if data.empty:
            raise ValueError("Price data is empty")

        # 初始化
        portfolio = Portfolio(cash=self.config.initial_cash)
        strategy.initialize()

        history_records = []
        all_trades = []

        logger.info(f"Starting backtest: {len(data)} days, {len(data.columns)} assets")

        # 遍历每个交易日
        for i, (date, prices) in enumerate(data.iterrows()):
            current_date = pd.to_datetime(date)
            current_prices = prices.dropna().to_dict()

            # 获取到当前日期的历史数据
            lookback_data = data.iloc[: i + 1]

            # 策略生成信号
            signals = strategy.on_data(lookback_data, portfolio, current_date)

            # 执行交易
            for signal in signals:
                trade = self._execute_signal(signal, portfolio, current_prices, current_date)
                if trade:
                    all_trades.append(trade)

            # 记录每日状态
            record = self._record_state(portfolio, current_prices, current_date)
            history_records.append(record)

            # 触发回调
            for callback in self._callbacks:
                callback(i, len(data), portfolio, current_date)

        # 构建结果
        history_df = pd.DataFrame(history_records)
        trades_df = pd.DataFrame(all_trades) if all_trades else pd.DataFrame()

        # 计算指标
        metrics = calculate_metrics(history_df)

        logger.info(f"Backtest completed: {metrics.total_return:.2%} total return")

        return BacktestResult(
            config=self.config,
            portfolio=portfolio,
            history=history_df,
            trades=trades_df,
            metrics=metrics,
        )

    def _execute_signal(
        self,
        signal: Signal,
        portfolio: Portfolio,
        prices: Dict[str, float],
        date: datetime,
    ) -> Optional[dict]:
        """执行交易信号"""
        symbol = signal.symbol
        price = prices.get(symbol)

        if price is None or price <= 0:
            logger.warning(f"No price for {symbol} on {date}")
            return None

        # 应用滑点
        if signal.action == "buy":
            executed_price = price * (1 + self.config.slippage)
        else:
            executed_price = price * (1 - self.config.slippage)

        # 计算数量
        if signal.quantity is not None:
            quantity = signal.quantity
        else:
            # 按权重计算
            target_value = portfolio.total_value(prices) * signal.weight
            quantity = target_value / executed_price

        if quantity <= 0:
            return None

        # 执行交易
        asset = Asset(symbol=symbol)

        if signal.action == "buy":
            cost = quantity * executed_price
            commission = cost * self.config.commission_rate
            total_cost = cost + commission

            if total_cost > portfolio.cash:
                logger.warning(f"Insufficient cash for buying {symbol}")
                return None

            portfolio.cash -= total_cost
            portfolio.add_position(asset, quantity, executed_price, date)

        elif signal.action == "sell":
            position = portfolio.get_position(symbol)
            if not position or position.quantity < quantity:
                logger.warning(f"Insufficient position for selling {symbol}")
                return None

            proceeds = quantity * executed_price
            commission = proceeds * self.config.commission_rate
            net_proceeds = proceeds - commission

            portfolio.cash += net_proceeds
            portfolio.remove_position(symbol, quantity)
        else:
            return None

        return {
            "date": date,
            "symbol": symbol,
            "action": signal.action,
            "quantity": quantity,
            "price": executed_price,
            "commission": commission,
        }

    def _record_state(
        self,
        portfolio: Portfolio,
        prices: Dict[str, float],
        date: datetime,
    ) -> dict:
        """记录每日状态"""
        total_value = portfolio.total_value(prices)
        position_value = total_value - portfolio.cash

        weights = portfolio.weights(prices)

        record = {
            "date": date,
            "cash": portfolio.cash,
            "position_value": position_value,
            "total_value": total_value,
        }

        # 添加各资产权重
        for symbol in portfolio.symbols:
            record[f"weight_{symbol}"] = weights.get(symbol, 0.0)

        return record
