"""
Shared pytest configuration and fixtures for openstrategy data-source tests.

Unit tests mock all external network calls.
Integration tests are gated by the `integration` marker and only run when
requested via `pytest -m integration` or the env var `OPENSTRATEGY_INTEGRATION=1`.
"""

import os
from datetime import datetime

import pandas as pd
import pytest


def _integration_enabled() -> bool:
    """Return True if integration tests should run."""
    return os.environ.get("OPENSTRATEGY_INTEGRATION", "0").lower() in ("1", "true", "yes")


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: tests that hit real APIs/network")


def pytest_runtest_setup(item):
    """Skip integration tests unless explicitly enabled."""
    if item.get_closest_marker("integration") and not _integration_enabled():
        pytest.skip("integration tests disabled (set OPENSTRATEGY_INTEGRATION=1)")


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Return a small OHLCV DataFrame with a DatetimeIndex."""
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


@pytest.fixture
def sample_yahoo_history() -> pd.DataFrame:
    """Return a DataFrame that mimics yfinance Ticker.history() output."""
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "High": [105.0, 106.0, 107.0, 108.0, 109.0],
            "Low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "Close": [104.0, 105.0, 106.0, 107.0, 108.0],
            "Volume": [1000, 1100, 1200, 1300, 1400],
            "Dividends": [0.0, 0.0, 0.0, 0.0, 0.0],
            "Stock Splits": [0.0, 0.0, 0.0, 0.0, 0.0],
        },
        index=dates,
    )


@pytest.fixture
def sample_akshare_response() -> pd.DataFrame:
    """Return a DataFrame that mimics akshare stock_zh_a_hist output."""
    return pd.DataFrame(
        {
            "日期": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "开盘": [100.0, 101.0, 102.0],
            "收盘": [104.0, 105.0, 106.0],
            "最高": [105.0, 106.0, 107.0],
            "最低": [99.0, 100.0, 101.0],
            "成交量": [1000, 1100, 1200],
            "成交额": [100000.0, 110000.0, 120000.0],
        }
    )
