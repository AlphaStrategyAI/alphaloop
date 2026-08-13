"""
CLI tests for alphaloop.

These tests exercise the argument parser and command dispatch without
hitting the network. End-to-end real-data smoke tests live in
examples/demo_real_data.py.
"""
from __future__ import annotations

from unittest import mock

import pandas as pd
import pytest

import importlib

from alphaloop.cli.commands import (
    fetch_data,
    optimize_strategy,
    run_backtest,
)

# Import the cli.main submodule directly. We can't use
# `from alphaloop.cli import main` here because the package's
# __init__.py re-exports a `main` *function* under the same name, and
# `from package import name` resolves to attributes first — so the
# function would shadow the submodule. Using importlib ensures we get
# the module object, then we pull `.main` (the callable) off it.
_cli_main_module = importlib.import_module("alphaloop.cli.main")
cli_main = _cli_main_module.main


def test_cli_help_exits_cleanly(capsys):
    """`alphaloop` with no args should print help and return 1."""
    rc = cli_main([])
    assert rc == 1
    out = capsys.readouterr().out
    assert "OpenStrategy" in out
    assert "backtest" in out
    assert "fetch" in out


def test_cli_fetch_calls_yahoo(tmp_path):
    """`alphaloop fetch --symbol AAPL --source yahoo --period 5d` should
    call YahooFinanceSource.get_data and return 0."""
    fake_df = pd.DataFrame(
        {"open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5], "volume": [100]},
        index=pd.date_range("2024-01-01", periods=1),
    )

    with mock.patch(
        "alphaloop.cli.commands.YahooFinanceSource"
    ) as MockYahoo:
        instance = MockYahoo.return_value
        instance.get_data.return_value = fake_df

        output = tmp_path / "aapl.csv"
        rc = cli_main(
            [
                "fetch",
                "--symbol",
                "AAPL",
                "--source",
                "yahoo",
                "--period",
                "5d",
                "--output",
                str(output),
            ]
        )

        assert rc == 0
        instance.get_data.assert_called_once()
        kwargs = instance.get_data.call_args.kwargs
        assert kwargs["start"] is None
        assert kwargs["end"] is None
        assert kwargs["period"] == "5d"
        assert output.exists()


def test_cli_fetch_rejects_unknown_source():
    """Unknown data source should fail in argparse (choices validation)."""
    with pytest.raises(SystemExit):
        cli_main(
            [
                "fetch",
                "--symbol",
                "AAPL",
                "--source",
                "bogus",
                "--period",
                "5d",
            ]
        )


def test_cli_fetch_json_output(tmp_path):
    """JSON output path should produce a JSON file with metadata."""
    fake_df = pd.DataFrame(
        {"open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5], "volume": [100]},
        index=pd.date_range("2024-01-01", periods=1),
    )
    with mock.patch(
        "alphaloop.cli.commands.YahooFinanceSource"
    ) as MockYahoo:
        MockYahoo.return_value.get_data.return_value = fake_df

        output = tmp_path / "aapl.json"
        rc = cli_main(
            [
                "fetch",
                "--symbol",
                "AAPL",
                "--source",
                "yahoo",
                "--period",
                "5d",
                "--output",
                str(output),
            ]
        )
        assert rc == 0

    import json

    payload = json.loads(output.read_text())
    assert payload["symbol"] == "AAPL"
    assert payload["source"] == "yahoo"
    assert payload["rows"] == 1
    assert isinstance(payload["data"], list)


def test_cli_fetch_ccxt_uses_exchange_arg(tmp_path):
    """--exchange should be passed through to CCXTSource when source=ccxt."""
    fake_df = pd.DataFrame(
        {"open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5], "volume": [100]},
        index=pd.date_range("2024-01-01", periods=1),
    )

    with mock.patch("alphaloop.data.ccxt.CCXTSource") as MockCCXT:
        MockCCXT.return_value.get_data.return_value = fake_df

        rc = cli_main(
            [
                "fetch",
                "--symbol",
                "BTC/USDT",
                "--source",
                "ccxt",
                "--exchange",
                "binance",
                "--period",
                "5d",
            ]
        )
        assert rc == 0
        MockCCXT.assert_called_once()
        kwargs = MockCCXT.call_args.kwargs
        assert kwargs["exchange"] == "binance"
        # Public market data shouldn't need a proxy by default.
        assert kwargs["use_proxy"] is False