"""
Yahoo Finance 数据源
"""

import logging
from datetime import datetime
from typing import Optional, Union

import pandas as pd
import yfinance as yf

from .base import DataSource, DataSourceError

logger = logging.getLogger(__name__)


class YahooFinanceSource(DataSource):
    """
    Yahoo Finance 数据源

    支持全球股票、ETF、加密货币数据获取

    Examples:
        >>> source = YahooFinanceSource()
        >>> df = source.get_data("AAPL", period="1y")
        >>> print(df.tail())
    """

    def __init__(self, cache=None):
        super().__init__(name="yahoo", cache=cache)

    def get_data(
        self,
        symbol: str,
        start: Optional[Union[str, datetime]] = None,
        end: Optional[Union[str, datetime]] = None,
        period: Optional[str] = None,
        interval: str = "1d",
        **kwargs,
    ) -> pd.DataFrame:
        """
        获取 Yahoo Finance 数据

        Args:
            symbol: 资产代码（如 "AAPL", "VTI", "BTC-USD"）
            start: 开始日期
            end: 结束日期
            period: 简写周期 ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")
            interval: 数据间隔 ("1d", "1wk", "1mo")

        Returns:
            DataFrame with columns: [open, high, low, close, volume, dividends, splits]
        """
        symbol = self.normalize_symbol(symbol)

        try:
            ticker = yf.Ticker(symbol)

            # 使用 period 或 start/end
            if period:
                hist = ticker.history(period=period, interval=interval)
            else:
                start, end = self._parse_dates(start, end)
                hist = ticker.history(start=start, end=end, interval=interval)

            if hist.empty:
                raise DataSourceError(f"No data returned for {symbol}")

            # 标准化列名
            hist = hist.rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                    "Dividends": "dividends",
                    "Stock Splits": "splits",
                }
            )

            # 确保基本列存在
            for col in ["open", "high", "low", "close", "volume"]:
                if col not in hist.columns:
                    hist[col] = 0.0

            logger.debug(f"Fetched {len(hist)} rows for {symbol}")
            return hist

        except Exception as e:
            raise DataSourceError(f"Failed to fetch {symbol} from Yahoo Finance: {e}")

    def get_info(self, symbol: str) -> dict:
        """
        获取资产基本信息

        Args:
            symbol: 资产代码

        Returns:
            资产信息字典
        """
        symbol = self.normalize_symbol(symbol)
        ticker = yf.Ticker(symbol)
        return ticker.info

    def search(self, query: str, limit: int = 10) -> list:
        """
        搜索资产

        Args:
            query: 搜索关键词
            limit: 返回结果数量

        Returns:
            搜索结果列表
        """
        # yfinance 没有直接搜索，返回空列表
        logger.warning("YahooFinanceSource.search() not implemented")
        return []
