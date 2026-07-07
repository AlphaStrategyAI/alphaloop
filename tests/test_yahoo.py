"""
Unit tests for the Yahoo Finance data source.
"""

from unittest import mock

import pandas as pd
import pytest

from openstrategy.data.base import DataSourceError
from openstrategy.data.yahoo import YahooFinanceSource


def test_normalize_symbol():
    source = YahooFinanceSource()
    assert source.normalize_symbol("aapl") == "AAPL"
    assert source.normalize_symbol(" BTC-USD ") == "BTC-USD"


@mock.patch("openstrategy.data.yahoo.yf.Ticker")
def test_get_data_with_period(mock_ticker_cls, sample_yahoo_history):
    mock_ticker = mock_ticker_cls.return_value
    mock_ticker.history.return_value = sample_yahoo_history

    source = YahooFinanceSource()
    df = source.get_data("AAPL", period="1mo")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert list(df.columns[:5]) == ["open", "high", "low", "close", "volume"]
    mock_ticker.history.assert_called_once_with(period="1mo", interval="1d")


@mock.patch("openstrategy.data.yahoo.yf.Ticker")
def test_get_data_with_dates(mock_ticker_cls, sample_yahoo_history):
    mock_ticker = mock_ticker_cls.return_value
    mock_ticker.history.return_value = sample_yahoo_history

    source = YahooFinanceSource()
    df = source.get_data("VTI", start="2024-01-01", end="2024-01-05")

    assert not df.empty
    assert "close" in df.columns
    _, call_kwargs = mock_ticker.history.call_args
    assert "start" in call_kwargs and "end" in call_kwargs


@mock.patch("openstrategy.data.yahoo.yf.Ticker")
def test_get_data_empty_raises(mock_ticker_cls):
    mock_ticker = mock_ticker_cls.return_value
    mock_ticker.history.return_value = pd.DataFrame()

    source = YahooFinanceSource()
    with pytest.raises(DataSourceError, match="No data returned"):
        source.get_data("AAPL", period="1mo")


@mock.patch("openstrategy.data.yahoo.yf.Ticker")
def test_get_info(mock_ticker_cls):
    mock_ticker = mock_ticker_cls.return_value
    mock_ticker.info = {"symbol": "AAPL", "name": "Apple Inc."}

    source = YahooFinanceSource()
    info = source.get_info("AAPL")
    assert info["symbol"] == "AAPL"


def test_search_returns_empty_list():
    source = YahooFinanceSource()
    assert source.search("AAPL") == []


@mock.patch("openstrategy.data.yahoo.yf.Ticker")
def test_get_data_adds_missing_columns(mock_ticker_cls):
    # history returns only close -> source fills missing OHLCV columns
    df = pd.DataFrame({"Close": [100.0, 101.0]}, index=pd.date_range("2024-01-01", periods=2))
    mock_ticker = mock_ticker_cls.return_value
    mock_ticker.history.return_value = df

    source = YahooFinanceSource()
    result = source.get_data("AAPL", period="5d")
    for col in ["open", "high", "low", "close", "volume"]:
        assert col in result.columns
