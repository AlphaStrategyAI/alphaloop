"""
投资组合类 - 管理多个资产仓位的集合
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterator, List, Optional

import pandas as pd

from .asset import Asset
from .position import Position

logger = logging.getLogger(__name__)


@dataclass
class Portfolio:
    """
    投资组合类，管理多个资产的仓位。

    Attributes:
        name: 组合名称
        positions: 仓位字典，key 为 symbol，value 为 Position
        cash: 现金余额
        base_currency: 基础货币

    Examples:
        >>> from .asset import Asset
        >>> portfolio = Portfolio(name="60/40组合", cash=100000.0)
        >>> stock = Asset(symbol="VTI")
        >>> bond = Asset(symbol="BND")
        >>> portfolio.add_position(stock, 100.0, 200.0)
        >>> portfolio.add_position(bond, 200.0, 80.0)
        >>> portfolio.total_value({'VTI': 210.0, 'BND': 82.0})
        57400.0
    """

    name: str = "Portfolio"
    positions: Dict[str, Position] = field(default_factory=dict)
    cash: float = 0.0
    base_currency: str = "USD"
    created_at: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        n_positions = len(self.positions)
        return f"Portfolio('{self.name}', {n_positions} positions, cash={self.cash:.2f})"

    def __iter__(self) -> Iterator[Position]:
        """迭代所有仓位"""
        return iter(self.positions.values())

    def __len__(self) -> int:
        """仓位数量"""
        return len(self.positions)

    def __contains__(self, symbol: str) -> bool:
        """是否持有某资产"""
        return symbol.upper() in self.positions

    def __getitem__(self, symbol: str) -> Position:
        """通过 symbol 获取仓位"""
        return self.positions[symbol.upper()]

    @property
    def symbols(self) -> List[str]:
        """获取所有持仓的 symbol 列表"""
        return list(self.positions.keys())

    @property
    def assets(self) -> List[Asset]:
        """获取所有持仓的 Asset 列表"""
        return [pos.asset for pos in self.positions.values()]

    @property
    def has_positions(self) -> bool:
        """是否有任何持仓"""
        return len(self.positions) > 0

    def get_position(self, symbol: str) -> Optional[Position]:
        """
        获取指定资产的仓位

        Args:
            symbol: 资产代码

        Returns:
            Position 对象，如果不存在则返回 None
        """
        return self.positions.get(symbol.upper())

    def has_position(self, symbol: str) -> bool:
        """是否持有指定资产"""
        symbol = symbol.upper()
        return symbol in self.positions and not self.positions[symbol].is_empty

    def add_position(
        self, asset: Asset, quantity: float, price: float, date: Optional[datetime] = None
    ) -> None:
        """
        增加/创建仓位

        Args:
            asset: 资产对象
            quantity: 数量
            price: 成交价格
            date: 交易日期
        """
        symbol = asset.symbol.upper()

        if symbol in self.positions:
            # 增加现有仓位
            self.positions[symbol].add_quantity(quantity, price)
        else:
            # 新建仓位
            self.positions[symbol] = Position(
                asset=asset,
                quantity=quantity,
                entry_price=price,
                entry_date=date or datetime.now(),
            )

        logger.debug(f"Added {quantity} {symbol} @ {price}")

    def remove_position(self, symbol: str, quantity: float) -> None:
        """
        减少仓位

        Args:
            symbol: 资产代码
            quantity: 减少数量
        """
        symbol = symbol.upper()

        if symbol not in self.positions:
            raise ValueError(f"没有持仓 {symbol}")

        self.positions[symbol].reduce_quantity(quantity)

        # 如果空仓了，移除该仓位
        if self.positions[symbol].is_empty:
            del self.positions[symbol]

    def set_position(
        self, asset: Asset, target_quantity: float, price: float, date: Optional[datetime] = None
    ) -> float:
        """
        设置目标仓位（用于再平衡）

        Args:
            asset: 资产对象
            target_quantity: 目标数量
            price: 当前价格
            date: 日期

        Returns:
            实际交易量（正数为买入，负数为卖出）
        """
        symbol = asset.symbol.upper()
        current_qty = self.positions[symbol].quantity if symbol in self.positions else 0.0
        delta = target_quantity - current_qty

        if abs(delta) < 1e-10:
            return 0.0  # 无需调整

        if delta > 0:
            # 买入
            self.add_position(asset, delta, price, date)
        else:
            # 卖出
            self.remove_position(symbol, abs(delta))

        return delta

    def total_value(self, prices: Dict[str, float]) -> float:
        """
        计算组合总价值（持仓 + 现金）

        Args:
            prices: 价格字典，key 为 symbol

        Returns:
            总价值
        """
        position_value = 0.0

        for symbol, position in self.positions.items():
            price = prices.get(symbol)
            if price is None:
                logger.warning(f"Missing price for {symbol}")
                continue
            position_value += position.market_value(price)

        return position_value + self.cash

    def position_values(self, prices: Dict[str, float]) -> Dict[str, float]:
        """
        计算各仓位的市场价值

        Args:
            prices: 价格字典

        Returns:
            各仓位价值的字典
        """
        values = {}
        for symbol, position in self.positions.items():
            price = prices.get(symbol, 0.0)
            values[symbol] = position.market_value(price)
        return values

    def weights(self, prices: Dict[str, float]) -> Dict[str, float]:
        """
        计算各仓位的权重

        Args:
            prices: 价格字典

        Returns:
            各仓位权重的字典
        """
        total = self.total_value(prices)

        if total <= 0:
            return {symbol: 0.0 for symbol in self.positions}

        values = self.position_values(prices)
        return {symbol: value / total for symbol, value in values.items()}

    def target_weights_to_quantities(
        self, target_weights: Dict[str, float], prices: Dict[str, float]
    ) -> Dict[str, float]:
        """
        将目标权重转换为目标数量

        Args:
            target_weights: 目标权重字典
            prices: 当前价格字典

        Returns:
            目标数量字典
        """
        total_value = self.total_value(prices)
        quantities = {}

        for symbol, weight in target_weights.items():
            price = prices.get(symbol)
            if price is None or price <= 0:
                logger.warning(f"Invalid price for {symbol}: {price}")
                quantities[symbol] = 0.0
                continue

            target_value = total_value * weight
            quantities[symbol] = target_value / price

        return quantities

    def deviation_from_target(
        self, target_weights: Dict[str, float], prices: Dict[str, float]
    ) -> Dict[str, float]:
        """
        计算当前权重与目标权重的偏离

        Args:
            target_weights: 目标权重
            prices: 当前价格

        Returns:
            各资产的偏离值（当前 - 目标）
        """
        current_weights = self.weights(prices)
        deviation = {}

        all_symbols = set(current_weights.keys()) | set(target_weights.keys())

        for symbol in all_symbols:
            current = current_weights.get(symbol, 0.0)
            target = target_weights.get(symbol, 0.0)
            deviation[symbol] = current - target

        return deviation

    def max_deviation(self, target_weights: Dict[str, float], prices: Dict[str, float]) -> float:
        """
        计算最大偏离值（绝对值）

        Args:
            target_weights: 目标权重
            prices: 当前价格

        Returns:
            最大偏离值的绝对值
        """
        deviations = self.deviation_from_target(target_weights, prices)
        if not deviations:
            return 0.0
        return max(abs(d) for d in deviations.values())

    def rebalance(
        self,
        target_weights: Dict[str, float],
        prices: Dict[str, float],
        date: Optional[datetime] = None,
        tolerance: float = 0.001,
    ) -> Dict[str, float]:
        """
        执行再平衡到目标权重

        Args:
            target_weights: 目标权重字典
            prices: 当前价格字典
            date: 交易日期
            tolerance: 最小交易阈值（避免过小的交易）

        Returns:
            实际执行的交易量字典
        """
        trades = {}
        quantities = self.target_weights_to_quantities(target_weights, prices)

        for symbol, target_qty in quantities.items():
            # 获取或创建 Asset 对象
            if symbol in self.positions:
                asset = self.positions[symbol].asset
            else:
                # 需要创建新的 Asset 对象
                # 这里简化处理，实际使用时可能需要更多信息
                asset = Asset(symbol=symbol)

            price = prices.get(symbol, 0.0)
            if price <= 0:
                continue

            current_qty = self.positions[symbol].quantity if symbol in self.positions else 0.0
            delta = target_qty - current_qty

            # 检查是否超过交易阈值
            if abs(delta) * price < tolerance * self.total_value(prices):
                continue

            actual_delta = self.set_position(asset, target_qty, price, date)
            trades[symbol] = actual_delta

        if trades:
            logger.info(f"Rebalanced {len(trades)} positions: {trades}")

        return trades

    def to_dataframe(self, prices: Dict[str, float]) -> pd.DataFrame:
        """
        将组合信息转换为 DataFrame

        Args:
            prices: 当前价格字典

        Returns:
            包含仓位信息的 DataFrame
        """
        if not self.positions:
            return pd.DataFrame()

        weights = self.weights(prices)
        values = self.position_values(prices)

        data = []
        for symbol, position in self.positions.items():
            price = prices.get(symbol, 0.0)
            data.append(
                {
                    "symbol": symbol,
                    "asset_class": position.asset.asset_class.name,
                    "quantity": position.quantity,
                    "price": price,
                    "market_value": values.get(symbol, 0.0),
                    "weight": weights.get(symbol, 0.0),
                    "entry_price": position.entry_price,
                    "unrealized_pnl": position.unrealized_pnl(price),
                }
            )

        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values("market_value", ascending=False)

        return df

    def copy(self) -> Portfolio:
        """创建组合的深拷贝"""
        return Portfolio(
            name=self.name,
            positions={s: p.copy() for s, p in self.positions.items()},
            cash=self.cash,
            base_currency=self.base_currency,
            created_at=self.created_at,
        )

    def summary(self, prices: Dict[str, float]) -> dict:
        """
        获取组合摘要信息

        Args:
            prices: 当前价格字典

        Returns:
            摘要字典
        """
        total = self.total_value(prices)
        position_value = total - self.cash

        return {
            "name": self.name,
            "total_value": total,
            "cash": self.cash,
            "cash_ratio": self.cash / total if total > 0 else 0.0,
            "position_value": position_value,
            "n_positions": len(self.positions),
            "n_assets": len(set(p.asset.symbol for p in self.positions.values())),
        }
