"""
模拟经纪商 - 处理交易执行
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """订单"""

    symbol: str
    action: str  # "buy", "sell"
    quantity: float
    order_type: str = "market"  # "market", "limit"
    limit_price: Optional[float] = None
    timestamp: Optional[datetime] = None


@dataclass
class Trade:
    """成交记录"""

    symbol: str
    action: str
    quantity: float
    price: float
    commission: float
    timestamp: datetime


class SimulatedBroker:
    """
    模拟经纪商

    模拟交易执行，计算佣金和滑点

    Examples:
        >>> broker = SimulatedBroker(commission_rate=0.001)
        >>> trade = broker.execute_order(order, price=100.0)
    """

    def __init__(
        self,
        commission_rate: float = 0.001,
        min_commission: float = 1.0,
        slippage: float = 0.0,
    ):
        """
        初始化模拟经纪商

        Args:
            commission_rate: 佣金费率
            min_commission: 最低佣金
            slippage: 滑点比例
        """
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.slippage = slippage

    def execute_order(
        self,
        order: Order,
        market_price: float,
        timestamp: Optional[datetime] = None,
    ) -> Optional[Trade]:
        """
        执行订单

        Args:
            order: 订单
            market_price: 市场价格
            timestamp: 时间戳

        Returns:
            成交记录或 None（如果无法执行）
        """
        if order.order_type == "market":
            executed_price = self._apply_slippage(market_price, order.action)
        elif order.order_type == "limit" and order.limit_price:
            executed_price = order.limit_price
        else:
            logger.warning(f"Unknown order type: {order.order_type}")
            return None

        # 计算佣金
        notional = order.quantity * executed_price
        commission = max(notional * self.commission_rate, self.min_commission)

        return Trade(
            symbol=order.symbol,
            action=order.action,
            quantity=order.quantity,
            price=executed_price,
            commission=commission,
            timestamp=timestamp or datetime.now(),
        )

    def _apply_slippage(self, price: float, action: str) -> float:
        """应用滑点"""
        if action == "buy":
            return price * (1 + self.slippage)
        else:
            return price * (1 - self.slippage)

    def calculate_cost(
        self,
        quantity: float,
        price: float,
        action: str,
    ) -> tuple:
        """
        计算交易成本

        Returns:
            (总成本, 佣金)
        """
        executed_price = self._apply_slippage(price, action)
        notional = quantity * executed_price
        commission = max(notional * self.commission_rate, self.min_commission)

        if action == "buy":
            total_cost = notional + commission
        else:
            total_cost = notional - commission

        return total_cost, commission
