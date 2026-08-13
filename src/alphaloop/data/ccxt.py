"""
CCXT 数据源 - 加密货币数据
"""

import logging
from datetime import datetime
from typing import Optional, Union

import pandas as pd

from .base import DataSource, DataSourceError

logger = logging.getLogger(__name__)


class CCXTSource(DataSource):
    """
    CCXT 数据源 - 获取加密货币数据

    支持 Binance, OKX, Coinbase 等交易所

    Examples:
        >>> source = CCXTSource(exchange="okx")  # 使用 OKX 替代 Binance
        >>> df = source.get_data("BTC/USDT", period="1mo")
        >>> print(df.tail())
    """

    def __init__(
        self,
        exchange: str = "okx",  # 默认使用 OKX（对中国用户更友好）
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        password: Optional[str] = None,
        use_proxy: bool = True,
        proxy_url: str = "http://127.0.0.1:7890",
        cache=None,
    ):
        """
        初始化 CCXT 数据源

        Args:
            exchange: 交易所名称 ("okx", "coinbase", "binance", etc.)
            api_key: API Key（可选，公开数据不需要）
            api_secret: API Secret（可选）
            password: 密码（部分交易所需要）
            use_proxy: 是否使用代理
            proxy_url: 代理地址
        """
        super().__init__(name=f"ccxt_{exchange}", cache=cache)
        self.exchange_id = exchange
        self.api_key = api_key
        self.api_secret = api_secret
        self.password = password
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url
        self._exchange = None

    def _get_exchange(self):
        """获取或创建交易所实例"""
        if self._exchange is None:
            try:
                import ccxt

                exchange_class = getattr(ccxt, self.exchange_id)
                config = {
                    "enableRateLimit": True,
                    "options": {"defaultType": "spot"},
                }

                # 配置代理
                if self.use_proxy:
                    config["proxies"] = {
                        "http": self.proxy_url,
                        "https": self.proxy_url,
                    }

                # 配置 API Key（如果需要）
                if self.api_key:
                    config["apiKey"] = self.api_key
                if self.api_secret:
                    config["secret"] = self.api_secret
                if self.password:
                    config["password"] = self.password

                self._exchange = exchange_class(config)
                self._exchange.load_markets()

            except ImportError:
                raise DataSourceError("ccxt not installed. Install with: pip install ccxt")
            except Exception as e:
                raise DataSourceError(f"Failed to initialize {self.exchange_id}: {e}")

        return self._exchange

    def get_data(
        self,
        symbol: str,
        start: Optional[Union[str, datetime]] = None,
        end: Optional[Union[str, datetime]] = None,
        period: Optional[str] = None,
        timeframe: str = "1d",
        **kwargs,
    ) -> pd.DataFrame:
        """
        获取加密货币 OHLCV 数据

        Args:
            symbol: 交易对（如 "BTC/USDT", "ETH/USDT"）
            start: 开始日期
            end: 结束日期
            period: 简写周期
            timeframe: K线周期 ("1m", "5m", "15m", "1h", "4h", "1d", "1w")

        Returns:
            DataFrame with columns: [open, high, low, close, volume]
        """
        exchange = self._get_exchange()
        symbol = self._normalize_symbol(symbol)

        # 检查交易对是否存在
        if symbol not in exchange.symbols:
            available = [s for s in exchange.symbols if symbol.split("/")[0] in s]
            raise DataSourceError(
                f"Symbol {symbol} not found on {self.exchange_id}. "
                f"Similar pairs: {available[:5]}"
            )

        try:
            # 解析日期
            start, end = self._parse_dates(start, end, period)

            # 获取 OHLCV 数据
            since = int(start.timestamp() * 1000)
            limit = 1000  # 最大获取条数

            end_ms = int(end.timestamp() * 1000)
            all_ohlcv = []
            while since < end_ms:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since, limit)
                if not ohlcv:
                    break
                # Keep candles whose open time is within the requested window.
                # End is inclusive — matches yfinance semantics used elsewhere
                # in alphaloop. ccxt sometimes returns the next bucket
                # after `end`, so we drop anything strictly past the end.
                ohlcv = [row for row in ohlcv if row[0] <= end_ms]
                if not ohlcv:
                    break
                all_ohlcv.extend(ohlcv)
                last_ts = ohlcv[-1][0]
                since = last_ts + 1
                if last_ts >= end_ms or len(ohlcv) < limit:
                    break

            if not all_ohlcv:
                raise DataSourceError(f"No data returned for {symbol}")

            # 转换为 DataFrame
            df = pd.DataFrame(
                all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

            # Convert timestamps. ccxt returns ms since epoch in UTC; mark
            # the index as UTC-aware so subsequent comparisons against
            # naive-local `start`/`end` datetimes do not silently drop rows
            # in non-UTC timezones.
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df = df.set_index("timestamp")

            # Re-project the user-supplied naive datetimes into the same UTC
            # timeline the data lives in. We deliberately drop tz-awareness
            # afterwards so the returned index stays plain (matches the rest
            # of alphaloop).
            # Re-project the user-supplied naive datetimes into the same UTC
            # timeline the data lives in. We deliberately drop tz-awareness
            # afterwards so the returned index stays plain (matches the rest
            # of alphaloop).
            local_tz = datetime.now().astimezone().tzinfo
            start_cmp = pd.Timestamp(start)
            end_cmp = pd.Timestamp(end)
            if start_cmp.tzinfo is None:
                start_cmp = start_cmp.tz_localize(local_tz).tz_convert("UTC")
            else:
                start_cmp = start_cmp.tz_convert("UTC")
            if end_cmp.tzinfo is None:
                end_cmp = end_cmp.tz_localize(local_tz).tz_convert("UTC")
            else:
                end_cmp = end_cmp.tz_convert("UTC")

            df = df[(df.index >= start_cmp) & (df.index <= end_cmp)]
            # Strip tz so the returned DatetimeIndex stays plain (matches the
            # rest of alphaloop). Use tz_convert(None) because the index
            # is already tz-aware — tz_localize(None) raises on aware data.
            df.index = df.index.tz_convert(None)

            # 移除重复
            df = df[~df.index.duplicated(keep="first")]

            logger.debug(f"Fetched {len(df)} rows for {symbol}")
            return df

        except Exception as e:
            raise DataSourceError(f"Failed to fetch {symbol} from {self.exchange_id}: {e}")

    def _normalize_symbol(self, symbol: str) -> str:
        """标准化交易对格式"""
        symbol = symbol.upper().strip()
        # 确保格式为 BASE/QUOTE
        if "-" in symbol and "/" not in symbol:
            symbol = symbol.replace("-", "/")
        if "/" not in symbol:
            # 默认为 USDT 交易对
            symbol = f"{symbol}/USDT"
        return symbol

    def get_tickers(self) -> list:
        """
        获取所有可交易的交易对

        Returns:
            交易对列表
        """
        exchange = self._get_exchange()
        return exchange.symbols

    def get_latest_price(self, symbol: str) -> float:
        """
        获取最新价格

        Args:
            symbol: 交易对

        Returns:
            最新价格
        """
        exchange = self._get_exchange()
        symbol = self._normalize_symbol(symbol)
        ticker = exchange.fetch_ticker(symbol)
        return ticker["last"]

    def search(self, query: str, limit: int = 10) -> list:
        """
        搜索交易对

        Args:
            query: 搜索关键词
            limit: 返回数量

        Returns:
            匹配的交易对列表
        """
        exchange = self._get_exchange()
        query = query.upper()
        matches = [s for s in exchange.symbols if query in s]
        return matches[:limit]
