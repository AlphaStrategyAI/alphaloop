"""
OpenBB 数据源 - 支持多资产类别和多市场数据

支持:
- 股票数据 (全球主要市场)
- ETF 数据
- 历史价格和技术指标

需要安装: pip install openbb
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from .base import DataSource, DataSourceError

logger = logging.getLogger(__name__)


class OpenBBDataSource(DataSource):
    """
    OpenBB 数据源 - 支持多资产类别和多市场数据

    支持:
    - 股票数据 (全球主要市场)
    - ETF 数据
    - 历史价格和技术指标
    - 自动批量请求处理
    - 数据缓存和错误重试

    当 OpenBB 不可用时，自动降级到 Yahoo Finance

    Examples:
        >>> from alphaloop.data import OpenBBDataSource
        >>> source = OpenBBDataSource()
        >>> df = source.get_data("VTI", start="2020-01-01", end="2024-01-01")
        >>> print(df.tail())

        >>> # 批量获取多个资产
        >>> prices = source.get_prices(["VTI", "VGK", "VPL"], period="1y")
    """

    # 重试配置
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # 秒

    # 支持的资产类型
    SUPPORTED_ASSET_TYPES = ["stock", "etf", "index", "crypto"]

    # 供应商优先级 (按可靠性排序)
    DEFAULT_PROVIDERS = ["yfinance", "fmp", "polygon", "alpha_vantage"]

    def __init__(
        self,
        cache=None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        enable_fallback: bool = True,
        retry_count: int = 3,
        retry_delay: float = 1.0,
        timeout: int = 30,
    ):
        """
        初始化 OpenBB 数据源

        Args:
            cache: 可选的数据缓存对象
            provider: 数据供应商 (yfinance, fmp, polygon, alpha_vantage)
                     None 表示自动选择
            api_key: API 密钥 (某些供应商需要)
            enable_fallback: 启用 Yahoo Finance 降级方案
            retry_count: 失败重试次数
            retry_delay: 重试间隔（秒）
            timeout: 请求超时时间
        """
        super().__init__(name="openbb", cache=cache)

        self.provider = provider
        self.api_key = api_key
        self.enable_fallback = enable_fallback
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.timeout = timeout

        # 内部状态
        self._obb = None
        self._fallback_source = None
        self._available = False
        self._initialized = False

        # 尝试初始化 OpenBB
        self._initialize()

        # Initialize fallback eagerly when enabled, so callers can recover
        # from runtime OpenBB failures even when the import succeeded.
        if self.enable_fallback and self._fallback_source is None:
            self._init_fallback()

    def _initialize(self) -> None:
        """初始化 OpenBB 连接"""
        if self._initialized:
            return

        try:
            from openbb import obb

            self._obb = obb
            # 测试 OpenBB 是否真正可用
            self._test_openbb()
            self._available = True
            self._initialized = True
            logger.info("OpenBB initialized successfully")

        except ImportError:
            self._available = False
            logger.warning("OpenBB not installed. Will use Yahoo Finance fallback.")

            if self.enable_fallback:
                self._init_fallback()

        except Exception as e:
            self._available = False
            logger.error(f"Failed to initialize OpenBB: {e}")

            if self.enable_fallback:
                self._init_fallback()

        self._initialized = True

    def _test_openbb(self) -> None:
        """测试 OpenBB 是否真正可用"""
        try:
            # 尝试一个简单的查询
            result = self._obb.equity.price.historical(symbol="AAPL", limit=5)
            if result is None:
                raise RuntimeError("OpenBB test query returned None")
        except Exception as e:
            raise RuntimeError(f"OpenBB test failed: {e}")

    def _init_fallback(self) -> None:
        """初始化降级数据源"""
        try:
            from .yahoo import YahooFinanceSource

            self._fallback_source = YahooFinanceSource(cache=self._cache)
            logger.info("Yahoo Finance fallback initialized")
        except Exception as e:
            logger.error(f"Failed to initialize fallback: {e}")

    @property
    def is_available(self) -> bool:
        """检查 OpenBB 是否可用"""
        return self._available

    @property
    def is_using_fallback(self) -> bool:
        """检查是否在使用降级方案"""
        return not self._available and self._fallback_source is not None

    def _with_retry(self, func, *args, **kwargs):
        """带重试机制的执行函数"""
        last_exception = None

        for attempt in range(self.retry_count):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1}/{self.retry_count} failed: {e}")

                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # 指数退避

        raise DataSourceError(f"All {self.retry_count} attempts failed: {last_exception}")

    def _fetch_with_openbb(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """使用 OpenBB 获取数据"""
        if not self._available or self._obb is None:
            raise DataSourceError("OpenBB not available")

        # 构建参数
        kwargs = {"symbol": symbol}

        if start:
            kwargs["start_date"] = start.strftime("%Y-%m-%d")
        if end:
            kwargs["end_date"] = end.strftime("%Y-%m-%d")

        # 设置供应商
        if self.provider:
            kwargs["provider"] = self.provider

        # 调用 OpenBB API
        try:
            # 使用股票历史数据端点
            result = self._obb.equity.price.historical(**kwargs)

            if result is None or hasattr(result, "empty") and result.empty:
                raise DataSourceError(f"No data returned for {symbol}")

            # 转换为 DataFrame
            if hasattr(result, "to_dataframe"):
                df = result.to_dataframe()
            elif hasattr(result, "results"):
                df = pd.DataFrame(result.results)
            else:
                df = pd.DataFrame(result)

            if df.empty:
                raise DataSourceError(f"Empty data for {symbol}")

            # 标准化列名
            df = self._normalize_columns(df)

            return df

        except Exception as e:
            raise DataSourceError(f"OpenBB fetch failed: {e}")

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名"""
        # 列名映射 (小写标准化)
        column_mapping = {
            # 常见变体
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "adj_close": "adj_close",
            "dividends": "dividends",
            "splits": "splits",
            # OpenBB 可能的变体
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "Adj Close": "adj_close",
            "adjClose": "adj_close",
            "AdjClose": "adj_close",
            "date": "date",
            "Date": "date",
            "timestamp": "date",
            "Timestamp": "date",
        }

        # 重命名存在的列
        rename_dict = {}
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                rename_dict[old_col] = new_col

        df = df.rename(columns=rename_dict)

        # 确保基本列存在
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = 0.0

        # 设置日期索引
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        elif df.index.name in ["date", "Date", "timestamp"]:
            df.index = pd.to_datetime(df.index)
            df.index.name = "date"

        # 确保索引是 datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        return df

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
        获取资产历史数据

        Args:
            symbol: 资产代码（如 "AAPL", "VTI", "BTC-USD"）
            start: 开始日期
            end: 结束日期
            period: 简写周期 ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")
            interval: 数据间隔 ("1d", "1wk", "1mo")
            **kwargs: 额外参数

        Returns:
            DataFrame with columns: [open, high, low, close, volume, adj_close]
            Index: datetime

        Raises:
            DataSourceError: 数据获取失败
        """
        symbol = self.normalize_symbol(symbol)

        # 检查缓存
        cache_key = f"{symbol}_{start}_{end}_{interval}"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {symbol}")
                return cached

        # 解析日期
        if period:
            start, end = self._parse_dates(period=period)
        else:
            start, end = self._parse_dates(start, end)

        # 尝试使用 OpenBB
        df = None

        if self._available:
            try:
                df = self._with_retry(self._fetch_with_openbb, symbol, start, end, interval)
                logger.debug(f"Fetched {len(df)} rows for {symbol} from OpenBB")
            except Exception as e:
                logger.warning(f"OpenBB failed for {symbol}: {e}")

        # 降级到 Yahoo Finance
        if df is None and self.enable_fallback and self._fallback_source:
            try:
                df = self._fallback_source.get_data(symbol, start=start, end=end, interval=interval)
                logger.debug(f"Fetched {len(df)} rows for {symbol} from fallback")
            except Exception as e:
                raise DataSourceError(f"Failed to fetch {symbol}: {e}")

        if df is None or df.empty:
            raise DataSourceError(f"No data available for {symbol}")

        # 缓存数据
        if self._cache:
            self._cache.set(cache_key, df)

        return df

    def get_batch_data(
        self,
        symbols: List[str],
        start: Optional[Union[str, datetime]] = None,
        end: Optional[Union[str, datetime]] = None,
        period: Optional[str] = None,
        interval: str = "1d",
        max_workers: int = 5,
    ) -> Dict[str, pd.DataFrame]:
        """
        批量获取多个资产的数据

        Args:
            symbols: 资产代码列表
            start: 开始日期
            end: 结束日期
            period: 简写周期
            interval: 数据间隔
            max_workers: 最大并发数

        Returns:
            字典: {symbol: DataFrame}
        """
        results = {}
        failed_symbols = []

        logger.info(f"Batch fetching {len(symbols)} symbols")

        # 顺序获取 (OpenBB 批量API支持有限)
        for i, symbol in enumerate(symbols, 1):
            try:
                logger.debug(f"Fetching {symbol} ({i}/{len(symbols)})")
                df = self.get_data(symbol, start=start, end=end, period=period, interval=interval)
                results[symbol] = df
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")
                failed_symbols.append(symbol)

            # 避免请求过快
            if i < len(symbols):
                time.sleep(0.1)

        if failed_symbols:
            logger.warning(f"Failed symbols: {failed_symbols}")

        logger.info(f"Successfully fetched {len(results)}/{len(symbols)} symbols")
        return results

    def get_prices(
        self,
        symbols: List[str],
        start: Optional[Union[str, datetime]] = None,
        end: Optional[Union[str, datetime]] = None,
        period: Optional[str] = None,
        price_col: str = "close",
    ) -> pd.DataFrame:
        """
        批量获取多个资产的收盘价

        Args:
            symbols: 资产代码列表
            start: 开始日期
            end: 结束日期
            price_col: 价格列名 (默认 "close")

        Returns:
            DataFrame with columns = symbols, index = dates
        """
        prices = {}

        for symbol in symbols:
            try:
                df = self.get_data(symbol, start=start, end=end, period=period)
                if not df.empty and price_col in df.columns:
                    prices[symbol] = df[price_col]
            except Exception as e:
                logger.warning(f"Failed to get {symbol}: {e}")

        if not prices:
            raise DataSourceError("No price data retrieved for any symbol")

        return pd.DataFrame(prices)

    def get_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取资产基本信息

        Args:
            symbol: 资产代码

        Returns:
            资产信息字典
        """
        symbol = self.normalize_symbol(symbol)

        if self._available and self._obb:
            try:
                result = self._obb.equity.profile(symbol=symbol)
                if hasattr(result, "results"):
                    return result.results[0] if result.results else {}
                return {}
            except Exception as e:
                logger.warning(f"OpenBB info failed: {e}")

        # 降级到 Yahoo Finance
        if self._fallback_source and hasattr(self._fallback_source, "get_info"):
            return self._fallback_source.get_info(symbol)

        return {}

    def search(
        self,
        query: str,
        limit: int = 10,
        asset_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        搜索资产

        Args:
            query: 搜索关键词
            limit: 返回结果数量
            asset_type: 资产类型过滤 (stock, etf, index, crypto)

        Returns:
            搜索结果列表
        """
        if not self._available or self._obb is None:
            logger.warning("OpenBB not available for search")
            return []

        try:
            # 使用 OpenBB 搜索
            result = self._obb.equity.search(query=query, limit=limit)

            if hasattr(result, "results"):
                results = result.results
            else:
                results = []

            # 过滤资产类型
            if asset_type and results:
                results = [r for r in results if r.get("type", "").lower() == asset_type.lower()]

            return results[:limit]

        except Exception as e:
            logger.warning(f"Search failed: {e}")
            return []

    def get_fundamentals(
        self,
        symbol: str,
        statement: str = "income",
        period: str = "annual",
        limit: int = 10,
    ) -> pd.DataFrame:
        """
        获取基本面数据

        Args:
            symbol: 资产代码
            statement: 报表类型 (income, balance, cash)
            period: 报告周期 (annual, quarter)
            limit: 返回条数

        Returns:
            DataFrame with fundamental data
        """
        if not self._available or self._obb is None:
            raise DataSourceError("OpenBB not available for fundamentals")

        symbol = self.normalize_symbol(symbol)

        try:
            if statement == "income":
                result = self._obb.equity.fundamental.income(
                    symbol=symbol, period=period, limit=limit
                )
            elif statement == "balance":
                result = self._obb.equity.fundamental.balance(
                    symbol=symbol, period=period, limit=limit
                )
            elif statement == "cash":
                result = self._obb.equity.fundamental.cash(
                    symbol=symbol, period=period, limit=limit
                )
            else:
                raise ValueError(f"Unknown statement type: {statement}")

            if hasattr(result, "to_dataframe"):
                return result.to_dataframe()
            elif hasattr(result, "results"):
                return pd.DataFrame(result.results)
            else:
                return pd.DataFrame(result)

        except Exception as e:
            raise DataSourceError(f"Failed to get fundamentals: {e}")

    def get_etf_holdings(
        self,
        symbol: str,
        limit: int = 50,
    ) -> pd.DataFrame:
        """
        获取 ETF 持仓数据

        Args:
            symbol: ETF代码
            limit: 返回条数

        Returns:
            DataFrame with holdings data
        """
        if not self._available or self._obb is None:
            raise DataSourceError("OpenBB not available for ETF holdings")

        symbol = self.normalize_symbol(symbol)

        try:
            result = self._obb.etf.holdings(symbol=symbol, limit=limit)

            if hasattr(result, "to_dataframe"):
                return result.to_dataframe()
            elif hasattr(result, "results"):
                return pd.DataFrame(result.results)
            else:
                return pd.DataFrame(result)

        except Exception as e:
            raise DataSourceError(f"Failed to get ETF holdings: {e}")

    def get_economic_indicators(
        self,
        indicator: str,
        country: str = "united_states",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取经济指标数据

        Args:
            indicator: 指标名称 (gdp, cpi, unemployment, etc.)
            country: 国家
            start: 开始日期
            end: 结束日期

        Returns:
            DataFrame with economic data
        """
        if not self._available or self._obb is None:
            raise DataSourceError("OpenBB not available for economic data")

        try:
            result = self._obb.economy.indicators(
                symbol=indicator,
                country=country,
                start_date=start,
                end_date=end,
            )

            if hasattr(result, "to_dataframe"):
                return result.to_dataframe()
            elif hasattr(result, "results"):
                return pd.DataFrame(result.results)
            else:
                return pd.DataFrame(result)

        except Exception as e:
            raise DataSourceError(f"Failed to get economic indicators: {e}")

    def get_status(self) -> Dict[str, Any]:
        """
        获取数据源状态

        Returns:
            状态信息字典
        """
        return {
            "name": self.name,
            "available": self._available,
            "using_fallback": self.is_using_fallback,
            "provider": self.provider,
            "retry_count": self.retry_count,
            "cache_enabled": self._cache is not None,
        }
