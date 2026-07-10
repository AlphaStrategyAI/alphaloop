"""
Unit tests for the AKShare (A-share) data source.
"""

from datetime import datetime
from unittest import mock

import pandas as pd
import pytest

from openstrategy.data.akshare import AKShareSource
from openstrategy.data.base import DataSourceError


def test_normalize_a_stock():
    source = AKShareSource()
    assert source._normalize_a_stock("600519.SH") == "600519"
    assert source._normalize_a_stock("000001.sz") == "000001"
    assert source._normalize_a_stock("  600519  ") == "600519"


def test_standardize_columns(sample_akshare_response):
    source = AKShareSource()
    df = source._standardize_columns(sample_akshare_response.copy())

    assert "open" in df.columns
    assert "close" in df.columns
    assert "high" in df.columns
    assert "low" in df.columns
    assert "volume" in df.columns
    assert isinstance(df.index, pd.DatetimeIndex)


def test_akshare_not_installed_raises():
    """When akshare is not installed, AKShareSource should raise DataSourceError.

    This test only makes sense when akshare is NOT importable. If
    the user has akshare installed (e.g. for integration tests),
    the test is skipped — there's no way to simulate the
    "not installed" state without uninstalling the package.
    """
    try:
        import akshare  # noqa: F401
    except ImportError:
        pass
    else:
        pytest.skip(
            "akshare is installed; cannot test the not-installed path. "
            "Re-run after `pip uninstall akshare` to actually exercise "
            "this branch."
        )
    source = AKShareSource()
    source._ak = None  # force re-import attempt
    with pytest.raises(DataSourceError, match="akshare not installed"):
        source._get_ak()


def test_get_data_with_period(sample_akshare_response):
    mock_ak = mock.MagicMock()
    mock_ak.stock_zh_a_hist.return_value = sample_akshare_response

    source = AKShareSource()
    source._ak = mock_ak

    df = source.get_data("600519", period="1mo")

    assert not df.empty
    assert "close" in df.columns
    mock_ak.stock_zh_a_hist.assert_called_once()
    _, kwargs = mock_ak.stock_zh_a_hist.call_args
    assert kwargs["symbol"] == "600519"
    assert kwargs["adjust"] == "qfq"


def test_get_data_empty_raises():
    mock_ak = mock.MagicMock()
    mock_ak.stock_zh_a_hist.return_value = pd.DataFrame()

    source = AKShareSource()
    source._ak = mock_ak

    with pytest.raises(DataSourceError, match="No data returned"):
        source.get_data("600519", start="2024-01-01", end="2024-01-05")


def test_get_index_data(sample_akshare_response):
    mock_ak = mock.MagicMock()
    mock_ak.index_zh_a_hist.return_value = sample_akshare_response

    source = AKShareSource()
    source._ak = mock_ak

    df = source.get_index_data("000300", start="2024-01-01", end="2024-01-05")

    assert not df.empty
    assert "close" in df.columns
    mock_ak.index_zh_a_hist.assert_called_once()


def test_search():
    mock_ak = mock.MagicMock()
    mock_ak.stock_zh_a_spot.return_value = pd.DataFrame(
        {
            "代码": ["600519", "000001"],
            "名称": ["贵州茅台", "平安银行"],
        }
    )

    source = AKShareSource()
    source._ak = mock_ak

    results = source.search("茅台")
    assert len(results) == 1
    assert results[0]["名称"] == "贵州茅台"
