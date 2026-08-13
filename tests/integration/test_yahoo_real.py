"""
Integration tests for the Yahoo Finance data source.

These tests hit the real Yahoo Finance API. Run with:

    OPENSTRATEGY_INTEGRATION=1 pytest tests/integration/ -v

Yahoo is rate-limited aggressively. If you get "Too Many Requests",
wait an hour or use a different network. Tests are designed to use
a small `period` (5d, 1mo) to keep the request light.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

# Mark all tests in this file as integration (gated by conftest).
# Run with: OPENSTRATEGY_INTEGRATION=1 pytest tests/integration/ -v
pytestmark = pytest.mark.integration

import pandas as pd  # noqa: E402

from alphaloop.data import YahooFinanceSource  # noqa: E402
from alphaloop.data.base import DataSourceError  # noqa: E402


@pytest.fixture
def yahoo_source() -> YahooFinanceSource:
    return YahooFinanceSource()


def test_yahoo_real_network_aapl_5d(yahoo_source):
    """Fetch AAPL 5-day history from real Yahoo Finance.

    Marked as integration so the unit-test run skips it. Set
    `OPENSTRATEGY_INTEGRATION=1` to enable.
    """
    df = yahoo_source.get_data("AAPL", period="5d")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "close" in df.columns
    assert df["close"].iloc[-1] > 0
    # AAPL trades in the $100-300 range in 2024-2026; sanity bound
    assert 50 < df["close"].iloc[-1] < 1000


def test_yahoo_real_network_msft_1mo(yahoo_source):
    """Fetch MSFT 1-month history.

    Bigger window but still light. Used to verify the source
    handles a non-default period without error.
    """
    df = yahoo_source.get_data("MSFT", period="1mo")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "close" in df.columns
    # MSFT 2024-2026 trades in the $300-500 range
    assert 100 < df["close"].iloc[-1] < 1000


def test_yahoo_real_network_invalid_symbol_raises(yahoo_source):
    """An invalid symbol should produce a DataSourceError, not silently empty data."""
    with pytest.raises(DataSourceError):
        yahoo_source.get_data("THIS_SYMBOL_SHOULD_NOT_EXIST_9999", period="5d")
