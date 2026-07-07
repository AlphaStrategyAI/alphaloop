"""
Unit tests for the CCXT cryptocurrency data source.
"""

from datetime import datetime, timedelta
from unittest import mock

import pandas as pd
import pytest

from openstrategy.data.base import DataSourceError
from openstrategy.data.ccxt import CCXTSource


def _make_mock_exchange(symbols, ohlcv):
    """Build a mock ccxt exchange object."""
    exchange = mock.MagicMock()
    exchange.symbols = symbols
    exchange.fetch_ohlcv.return_value = ohlcv
    exchange.fetch_ticker.return_value = {"last": 65000.0}
    return exchange


def _recent_ohlcv(days=3):
    """Return OHLCV rows whose timestamps fall within the last few days."""
    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return [
        [int((base - timedelta(days=days - i)).timestamp() * 1000),
         100.0 + i, 105.0 + i, 99.0 + i, 104.0 + i, 1000 + i]
        for i in range(days)
    ]


def test_normalize_symbol():
    source = CCXTSource(exchange="okx")
    assert source._normalize_symbol("btc-usdt") == "BTC/USDT"
    assert source._normalize_symbol("BTC/USDT") == "BTC/USDT"
    assert source._normalize_symbol("ETH") == "ETH/USDT"


def test_get_data_with_period():
    ohlcv = _recent_ohlcv(3)
    source = CCXTSource(exchange="okx", use_proxy=False)
    source._exchange = _make_mock_exchange(["BTC/USDT"], ohlcv)

    df = source.get_data("BTC", period="5d")

    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)


def test_get_data_with_dates():
    ohlcv = [
        [int(datetime(2024, 1, i).timestamp() * 1000), 100.0, 105.0, 99.0, 104.0, 1000]
        for i in range(1, 6)
    ]
    source = CCXTSource(exchange="okx", use_proxy=False)
    source._exchange = _make_mock_exchange(["BTC/USDT"], ohlcv)

    df = source.get_data("BTC/USDT", start="2024-01-01", end="2024-01-05")
    assert len(df) == 5


def test_get_data_symbol_not_found():
    source = CCXTSource(exchange="okx", use_proxy=False)
    source._exchange = _make_mock_exchange(["BTC/USDT"], [])

    with pytest.raises(DataSourceError, match="not found"):
        source.get_data("ETH", period="5d")


def test_get_data_empty_raises():
    source = CCXTSource(exchange="okx", use_proxy=False)
    source._exchange = _make_mock_exchange(["BTC/USDT"], [])

    with pytest.raises(DataSourceError, match="No data returned"):
        source.get_data("BTC/USDT", period="5d")


def test_get_tickers():
    source = CCXTSource(exchange="okx", use_proxy=False)
    source._exchange = _make_mock_exchange(["BTC/USDT", "ETH/USDT"], [])

    assert source.get_tickers() == ["BTC/USDT", "ETH/USDT"]


def test_get_latest_price():
    source = CCXTSource(exchange="okx", use_proxy=False)
    source._exchange = _make_mock_exchange(["BTC/USDT"], [])

    price = source.get_latest_price("BTC/USDT")
    assert price == 65000.0


def test_search():
    source = CCXTSource(exchange="okx", use_proxy=False)
    source._exchange = _make_mock_exchange(["BTC/USDT", "ETH/USDT", "BTC/EUR"], [])

    matches = source.search("ETH")
    assert matches == ["ETH/USDT"]


def test_ccxt_not_installed_raises():
    source = CCXTSource(exchange="okx", use_proxy=False)
    source._exchange = None
    with mock.patch.dict("sys.modules", {"ccxt": None}):
        with pytest.raises(DataSourceError, match="ccxt not installed"):
            source._get_exchange()
