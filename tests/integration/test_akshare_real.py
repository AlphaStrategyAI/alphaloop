"""
Integration tests for the AKShare data source (A-shares).

These tests hit the real AKShare API. Run with:

    OPENSTRATEGY_INTEGRATION=1 pytest tests/integration/ -v

AKShare is the easiest source to integration-test in the sandbox:
it pulls from a public Chinese data source, no API key required,
and rate limits are usually permissive.
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

from openstrategy.data import AKShareSource  # noqa: E402
from openstrategy.data.base import DataSourceError  # noqa: E402


@pytest.fixture
def akshare_source() -> AKShareSource:
    return AKShareSource()


def test_akshare_real_network_000001_7d(akshare_source):
    """Fetch 000001 (Ping An Bank) 7-day history from real AKShare."""
    df = akshare_source.get_data("000001", start="2024-01-01", end="2024-01-10")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    # AKShare returns Chinese column names; the source should
    # normalize to standard English columns
    assert "close" in df.columns
    # Ping An Bank trades in the 7-25 CNY range
    assert 5 < df["close"].iloc[-1] < 50


def test_akshare_real_network_600519_30d(akshare_source):
    """Fetch 600519 (Kweichow Moutai) 30-day history."""
    df = akshare_source.get_data("600519", start="2024-01-01", end="2024-02-01")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "close" in df.columns
    # Moutai trades in the 1300-2000 CNY range
    assert 500 < df["close"].iloc[-1] < 5000


def test_akshare_real_network_invalid_symbol_raises(akshare_source):
    """An invalid symbol should produce a DataSourceError."""
    with pytest.raises(DataSourceError):
        akshare_source.get_data("999999_NOT_A_REAL_STOCK", start="2024-01-01", end="2024-01-05")
