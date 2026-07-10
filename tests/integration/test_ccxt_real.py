"""
Integration tests for the CCXT data source (crypto).

These tests hit the real CCXT API. Run with:

    OPENSTRATEGY_INTEGRATION=1 pytest tests/integration/ -v

CCXT connects to public exchange APIs (no auth required for
read-only public market data). We use OKX as the default exchange;
override with the `exchange` kwarg if needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

# Mark all tests in this file as integration (gated by conftest).
# Run with: OPENSTRATEGY_INTEGRATION=1 pytest tests/integration/ -v
pytestmark = pytest.mark.integration

import pandas as pd  # noqa: E402

from openstrategy.data import CCXTSource  # noqa: E402
from openstrategy.data.base import DataSourceError  # noqa: E402


@pytest.fixture
def ccxt_source() -> CCXTSource:
    return CCXTSource()


def test_ccxt_real_network_btc_usdt_5d(ccxt_source):
    """Fetch BTC/USDT 5-day history from real OKX."""
    df = ccxt_source.get_data("BTC/USDT", exchange="okx", period="5d")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "close" in df.columns
    # BTC trades in the 20k-100k USD range
    assert 20_000 < df["close"].iloc[-1] < 200_000


def test_ccxt_real_network_eth_usdt_5d(ccxt_source):
    """Fetch ETH/USDT 5-day history."""
    df = ccxt_source.get_data("ETH/USDT", exchange="okx", period="5d")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "close" in df.columns
    # ETH trades in the 1k-5k USD range
    assert 500 < df["close"].iloc[-1] < 10_000


def test_ccxt_real_network_invalid_symbol_raises(ccxt_source):
    """An invalid symbol should produce a DataSourceError."""
    with pytest.raises(DataSourceError):
        ccxt_source.get_data("NOT_A_REAL_PAIR/XYZ", exchange="okx", period="1d")
