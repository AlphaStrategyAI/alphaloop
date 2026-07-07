"""
Unit tests for the OpenBB data source (with Yahoo Finance fallback).
"""

from unittest import mock

import pandas as pd
import pytest

from openstrategy.data.base import DataSourceError
from openstrategy.data.openbb_source import OpenBBDataSource


def _sample_openbb_df():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [105.0, 106.0, 107.0, 108.0, 109.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [104.0, 105.0, 106.0, 107.0, 108.0],
            "volume": [1000, 1100, 1200, 1300, 1400],
        },
        index=dates,
    )


def _make_obb_that_fails_on_historical():
    """
    Build an obb mock where the health-check query (limit=5) succeeds,
    but the real historical fetch (with start_date/end_date) raises.
    """
    def historical_side_effect(**kwargs):
        if kwargs.get("limit") == 5:
            result = mock.MagicMock()
            result.empty = False
            return result
        raise RuntimeError("OpenBB error")

    obb = mock.MagicMock()
    obb.equity.price.historical.side_effect = historical_side_effect
    return obb


def test_openbb_unavailable_uses_fallback():
    """When OpenBB import fails, the source should initialize a Yahoo fallback."""
    with mock.patch.dict("sys.modules", {"openbb": None}):
        source = OpenBBDataSource()
        assert not source.is_available
        assert source.is_using_fallback


def test_openbb_available_fetch_success():
    df = _sample_openbb_df()

    result = mock.MagicMock()
    result.empty = df.empty
    result.to_dataframe.return_value = df.copy()

    obb = mock.MagicMock()
    obb.equity.price.historical.return_value = result

    fake_module = mock.MagicMock()
    fake_module.obb = obb

    with mock.patch.dict("sys.modules", {"openbb": fake_module}):
        source = OpenBBDataSource()
        assert source.is_available
        result_df = source.get_data("AAPL", period="1mo")
        assert not result_df.empty
        assert "close" in result_df.columns


def test_openbb_fetch_falls_back_to_yahoo():
    """If OpenBB fetch fails, use Yahoo Finance fallback when enabled."""
    df = _sample_openbb_df()
    obb = _make_obb_that_fails_on_historical()

    fake_module = mock.MagicMock()
    fake_module.obb = obb

    with mock.patch.dict("sys.modules", {"openbb": fake_module}):
        source = OpenBBDataSource()
        assert source.is_available

        with mock.patch.object(source._fallback_source, "get_data", return_value=df):
            result_df = source.get_data("AAPL", period="1mo")
            assert not result_df.empty
            assert "close" in result_df.columns


def test_openbb_get_status():
    with mock.patch.dict("sys.modules", {"openbb": None}):
        source = OpenBBDataSource()
        status = source.get_status()
        assert status["name"] == "openbb"
        assert status["available"] is False
        assert status["using_fallback"] is True


def test_openbb_no_fallback_raises():
    df = _sample_openbb_df()
    obb = _make_obb_that_fails_on_historical()

    fake_module = mock.MagicMock()
    fake_module.obb = obb

    with mock.patch.dict("sys.modules", {"openbb": fake_module}):
        source = OpenBBDataSource(enable_fallback=False)
        source._available = True  # force available so it tries OpenBB
        source._fallback_source = None
        with pytest.raises(DataSourceError):
            source.get_data("AAPL", period="1mo")
