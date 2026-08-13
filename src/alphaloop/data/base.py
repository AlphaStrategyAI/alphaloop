"""
数据源基类 - 定义统一的数据接口
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)


class DataSourceError(Exception):
    """数据源错误"""

    pass


class DataSource(ABC):
    """
    数据源抽象基类

    所有具体数据源（Yahoo、AKShare、CCXT）都必须继承此类
    并实现 get_data 方法。

    Examples:
        >>> class MySource(DataSource):
        ...     def get_data(self, symbol, start, end):
        ...         # 实现数据获取逻辑
        ...         pass
    """

    def __init__(self, name: str = "base", cache=None):
        """
        初始化数据源

        Args:
            name: 数据源名称
            cache: 可选的数据缓存对象
        """
        self.name = name
        self._cache = cache
        self._supported_symbols: List[str] = []

    @abstractmethod
    def get_data(
        self,
        symbol: str,
        start: Optional[Union[str, datetime]] = None,
        end: Optional[Union[str, datetime]] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        获取资产历史数据

        Args:
            symbol: 资产代码（如 "AAPL", "600519.SH"）
            start: 开始日期，默认一年前
            end: 结束日期，默认今天
            **kwargs: 额外参数

        Returns:
            DataFrame with columns: [open, high, low, close, volume]
            Index: datetime

        Raises:
            DataSourceError: 数据获取失败
        """
        pass

    def get_latest_price(self, symbol: str) -> float:
        """
        获取最新价格

        Args:
            symbol: 资产代码

        Returns:
            最新收盘价
        """
        df = self.get_data(symbol, period="5d")
        if df.empty:
            raise DataSourceError(f"No data available for {symbol}")
        return float(df["close"].iloc[-1])

    def get_prices(
        self,
        symbols: List[str],
        start: Optional[Union[str, datetime]] = None,
        end: Optional[Union[str, datetime]] = None,
    ) -> pd.DataFrame:
        """
        批量获取多个资产的收盘价

        Args:
            symbols: 资产代码列表
            start: 开始日期
            end: 结束日期

        Returns:
            DataFrame with columns = symbols, index = dates
        """
        prices = {}
        for symbol in symbols:
            try:
                df = self.get_data(symbol, start, end)
                if not df.empty:
                    prices[symbol] = df["close"]
            except Exception as e:
                logger.warning(f"Failed to get data for {symbol}: {e}")

        if not prices:
            raise DataSourceError("No price data retrieved for any symbol")

        return pd.DataFrame(prices)

    def normalize_symbol(self, symbol: str) -> str:
        """
        标准化资产代码格式

        Args:
            symbol: 原始代码

        Returns:
            标准化后的代码
        """
        return symbol.upper().strip()

    def validate_symbol(self, symbol: str) -> bool:
        """
        验证资产代码是否有效

        Args:
            symbol: 资产代码

        Returns:
            是否有效
        """
        try:
            df = self.get_data(symbol, period="5d")
            return not df.empty
        except Exception:
            return False

    def _parse_dates(
        self,
        start: Optional[Union[str, datetime]] = None,
        end: Optional[Union[str, datetime]] = None,
        period: Optional[str] = None,
    ) -> tuple:
        """
        解析日期参数

        Args:
            start: 开始日期字符串或datetime
            end: 结束日期字符串或datetime
            period: 简写周期 ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")

        Returns:
            (start_datetime, end_datetime)
        """
        # 处理 period 简写
        if period:
            end = datetime.now()
            period_map = {
                "1d": 1,
                "5d": 5,
                "1mo": 30,
                "3mo": 90,
                "6mo": 180,
                "1y": 365,
                "2y": 730,
                "5y": 1825,
                "10y": 3650,
            }
            if period in period_map:
                start = end - timedelta(days=period_map[period])
            elif period == "ytd":
                start = datetime(end.year, 1, 1)
            elif period == "max":
                start = datetime(1970, 1, 1)

        # 默认时间范围
        if end is None:
            end = datetime.now()
        elif isinstance(end, str):
            end = pd.to_datetime(end)

        if start is None:
            start = end - timedelta(days=365)
        elif isinstance(start, str):
            start = pd.to_datetime(start)

        return start, end
