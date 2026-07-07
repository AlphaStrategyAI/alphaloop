"""
AKShare 数据源 - 中国A股数据
"""

import logging
from datetime import datetime
from typing import Optional, Union

import pandas as pd

from .base import DataSource, DataSourceError

logger = logging.getLogger(__name__)


class AKShareSource(DataSource):
    """
    AKShare 数据源 - 专门获取中国A股数据

    支持股票、指数、基金等数据

    Examples:
        >>> source = AKShareSource()
        >>> df = source.get_data("600519")  # 贵州茅台
        >>> print(df.tail())
    """

    def __init__(self, cache=None):
        super().__init__(name="akshare", cache=cache)
        self._ak = None  # 延迟导入

    def _get_ak(self):
        """延迟导入 akshare"""
        if self._ak is None:
            try:
                import akshare as ak

                self._ak = ak
            except ImportError:
                raise DataSourceError("akshare not installed. Install with: pip install akshare")
        return self._ak

    def get_data(
        self,
        symbol: str,
        start: Optional[Union[str, datetime]] = None,
        end: Optional[Union[str, datetime]] = None,
        period: Optional[str] = None,
        adjust: str = "qfq",  # 前复权
        **kwargs,
    ) -> pd.DataFrame:
        """
        获取 A 股历史数据

        Args:
            symbol: 股票代码（如 "600519", "000001"）
            start: 开始日期
            end: 结束日期
            period: 简写周期
            adjust: 复权方式 ("" 不复权, "qfq" 前复权, "hfq" 后复权)

        Returns:
            DataFrame with columns: [open, high, low, close, volume, amount]
        """
        ak = self._get_ak()
        symbol = self._normalize_a_stock(symbol)

        try:
            # 解析日期
            start, end = self._parse_dates(start, end, period)
            start_str = start.strftime("%Y%m%d")
            end_str = end.strftime("%Y%m%d")

            # 获取数据
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_str,
                end_date=end_str,
                adjust=adjust,
            )

            if df is None or df.empty:
                raise DataSourceError(f"No data returned for {symbol}")

            # 标准化列名和索引
            df = self._standardize_columns(df)

            logger.debug(f"Fetched {len(df)} rows for {symbol}")
            return df

        except Exception as e:
            raise DataSourceError(f"Failed to fetch {symbol} from AKShare: {e}")

    def _normalize_a_stock(self, symbol: str) -> str:
        """
        标准化 A 股代码

        去掉 .SH/.SZ 后缀，返回纯数字代码
        """
        symbol = symbol.upper().strip()
        for suffix in [".SH", ".SZ", ".BJ"]:
            if symbol.endswith(suffix):
                symbol = symbol.replace(suffix, "")
        return symbol

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名"""
        # AKShare 返回的列名映射
        column_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "涨跌幅": "pct_change",
            "涨跌额": "change",
            "换手率": "turnover",
        }

        df = df.rename(columns=column_map)

        # 设置日期索引
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")

        # 确保基本列存在
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = 0.0

        return df

    def get_stock_list(self) -> pd.DataFrame:
        """
        获取 A 股股票列表

        Returns:
            DataFrame with stock info
        """
        ak = self._get_ak()
        return ak.stock_zh_a_spot()

    def get_index_data(
        self,
        symbol: str = "000300",  # 沪深300
        start: Optional[Union[str, datetime]] = None,
        end: Optional[Union[str, datetime]] = None,
    ) -> pd.DataFrame:
        """
        获取指数数据

        Args:
            symbol: 指数代码（如 "000300" 沪深300, "000001" 上证指数）
            start: 开始日期
            end: 结束日期

        Returns:
            DataFrame with index data
        """
        ak = self._get_ak()
        start, end = self._parse_dates(start, end)

        try:
            df = ak.index_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
            return self._standardize_columns(df)
        except Exception as e:
            raise DataSourceError(f"Failed to fetch index {symbol}: {e}")

    def search(self, query: str, limit: int = 10) -> list:
        """
        搜索股票

        Args:
            query: 股票代码或名称
            limit: 返回数量

        Returns:
            搜索结果列表
        """
        try:
            df = self.get_stock_list()
            # 按代码或名称匹配
            mask = df["代码"].str.contains(query, case=False, na=False) | df["名称"].str.contains(
                query, case=False, na=False
            )
            results = df[mask].head(limit)
            return results.to_dict("records")
        except Exception as e:
            logger.warning(f"Search failed: {e}")
            return []
