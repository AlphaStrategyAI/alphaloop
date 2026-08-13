"""
资产类 - 表示一个可交易的资产
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .enums import AssetClass


@dataclass
class Asset:
    """
    资产类，表示一个可交易的金融资产。

    Attributes:
        symbol: 资产代码，如 "VTI", "BND"
        name: 资产名称
        asset_class: 资产类别
        currency: 计价货币，默认 "USD"
        exchange: 交易所
        metadata: 额外的元数据

    Examples:
        >>> stock = Asset(symbol="VTI", name="Vanguard Total Stock ETF",
        ...               asset_class=AssetClass.STOCK)
        >>> bond = Asset(symbol="BND", name="Vanguard Total Bond ETF",
        ...              asset_class=AssetClass.BOND)
    """

    symbol: str
    name: str = ""
    asset_class: AssetClass = AssetClass.STOCK
    currency: str = "USD"
    exchange: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """验证并规范化数据"""
        self.symbol = self.symbol.upper().strip()
        if not self.name:
            self.name = self.symbol

    def __hash__(self) -> int:
        """使用 symbol 作为哈希值，用于字典键"""
        return hash(self.symbol)

    def __eq__(self, other: object) -> bool:
        """两个资产相等当且仅当 symbol 相同"""
        if not isinstance(other, Asset):
            return NotImplemented
        return self.symbol == other.symbol

    def __repr__(self) -> str:
        return f"Asset(symbol='{self.symbol}', class={self.asset_class.name})"

    def __str__(self) -> str:
        return f"{self.symbol} ({self.name})"

    @property
    def is_equity(self) -> bool:
        """是否为权益类资产"""
        return self.asset_class == AssetClass.STOCK

    @property
    def is_fixed_income(self) -> bool:
        """是否为固定收益类资产"""
        return self.asset_class == AssetClass.BOND

    @property
    def is_cash(self) -> bool:
        """是否为现金"""
        return self.asset_class == AssetClass.CASH

    @classmethod
    def from_symbol(cls, symbol: str, asset_class: AssetClass = AssetClass.STOCK) -> Asset:
        """
        从 symbol 快速创建资产对象

        Args:
            symbol: 资产代码
            asset_class: 资产类别，默认股票

        Returns:
            Asset 实例
        """
        return cls(symbol=symbol, asset_class=asset_class)

    def to_dict(self) -> dict:
        """转换为字典表示"""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "asset_class": self.asset_class.name,
            "currency": self.currency,
            "exchange": self.exchange,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Asset:
        """从字典创建 Asset"""
        asset_class = AssetClass[data.get("asset_class", "STOCK")]
        return cls(
            symbol=data["symbol"],
            name=data.get("name", ""),
            asset_class=asset_class,
            currency=data.get("currency", "USD"),
            exchange=data.get("exchange"),
            metadata=data.get("metadata", {}),
        )
