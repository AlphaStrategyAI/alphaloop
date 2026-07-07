"""
仓位类 - 表示持有某个资产的数量和价值
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .asset import Asset


@dataclass
class Position:
    """
    仓位类，表示持有某个资产的数量。

    Attributes:
        asset: 资产对象
        quantity: 持有数量（份额/股数）
        entry_price: 入场价格（平均成本）
        entry_date: 入场日期

    Examples:
        >>> from .asset import Asset
        >>> asset = Asset(symbol="VTI")
        >>> pos = Position(asset=asset, quantity=100.0, entry_price=200.0)
        >>> pos.market_value(220.0)  # 当前价格 220
        22000.0
    """

    asset: Asset
    quantity: float = 0.0
    entry_price: Optional[float] = None
    entry_date: Optional[datetime] = None

    def __post_init__(self):
        """验证数据"""
        if self.quantity < 0:
            raise ValueError(f"持仓数量不能为负: {self.quantity}")

    def __repr__(self) -> str:
        return (
            f"Position({self.asset.symbol}, qty={self.quantity:.4f}, "
            f"avg_cost={self.entry_price})"
        )

    @property
    def is_empty(self) -> bool:
        """是否空仓"""
        return abs(self.quantity) < 1e-10

    @property
    def symbol(self) -> str:
        """资产代码快捷访问"""
        return self.asset.symbol

    def market_value(self, price: float) -> float:
        """
        计算当前市场价值

        Args:
            price: 当前价格

        Returns:
            市场价值
        """
        return self.quantity * price

    def unrealized_pnl(self, current_price: float) -> float:
        """
        计算未实现盈亏

        Args:
            current_price: 当前价格

        Returns:
            未实现盈亏金额
        """
        if self.entry_price is None:
            return 0.0
        return self.quantity * (current_price - self.entry_price)

    def unrealized_pnl_pct(self, current_price: float) -> float:
        """
        计算未实现盈亏百分比

        Args:
            current_price: 当前价格

        Returns:
            盈亏百分比（小数）
        """
        if self.entry_price is None or self.entry_price == 0:
            return 0.0
        return (current_price - self.entry_price) / self.entry_price

    def add_quantity(self, quantity: float, price: float) -> None:
        """
        增加持仓（买入），更新平均成本

        Args:
            quantity: 增加的数量
            price: 成交价格
        """
        if quantity <= 0:
            raise ValueError(f"增加数量必须为正: {quantity}")

        if self.entry_price is None:
            # 首次建仓
            self.quantity = quantity
            self.entry_price = price
        else:
            # 更新加权平均成本
            total_cost = self.quantity * self.entry_price + quantity * price
            self.quantity += quantity
            self.entry_price = total_cost / self.quantity if self.quantity > 0 else 0.0

    def reduce_quantity(self, quantity: float) -> None:
        """
        减少持仓（卖出）

        Args:
            quantity: 减少的数量

        Raises:
            ValueError: 如果减少数量超过当前持仓
        """
        if quantity <= 0:
            raise ValueError(f"减少数量必须为正: {quantity}")
        if quantity > self.quantity:
            raise ValueError(f"卖出数量 {quantity} 超过持仓 {self.quantity}")

        self.quantity -= quantity

        if self.is_empty:
            self.entry_price = None

    def weight(self, portfolio_value: float, price: float) -> float:
        """
        计算该仓位在组合中的权重

        Args:
            portfolio_value: 组合总价值
            price: 当前价格

        Returns:
            权重（小数，0-1）
        """
        if portfolio_value <= 0:
            return 0.0
        return self.market_value(price) / portfolio_value

    def copy(self) -> Position:
        """创建仓位的深拷贝"""
        return Position(
            asset=self.asset,
            quantity=self.quantity,
            entry_price=self.entry_price,
            entry_date=self.entry_date,
        )

    def to_dict(self, current_price: Optional[float] = None) -> dict:
        """
        转换为字典表示

        Args:
            current_price: 当前价格，用于计算市场价值
        """
        result = {
            "symbol": self.asset.symbol,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "entry_date": self.entry_date.isoformat() if self.entry_date else None,
        }

        if current_price is not None:
            result["current_price"] = current_price
            result["market_value"] = self.market_value(current_price)
            result["unrealized_pnl"] = self.unrealized_pnl(current_price)
            result["unrealized_pnl_pct"] = self.unrealized_pnl_pct(current_price)

        return result
