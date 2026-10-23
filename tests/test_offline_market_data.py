"""Offline market-data flag stays off unless a test turns it on."""

from __future__ import annotations

from datetime import date

import pytest

from engine.research.data_port import data_port_for_symbols
from engine.research.e2e_hooks import e2e_hold_running_seconds
from engine.research.offline_market_data import offline_market_data_enabled


def test_offline_market_data_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHALOOP_OFFLINE_MARKET_DATA", raising=False)
    assert offline_market_data_enabled() is False
    port = data_port_for_symbols(("AAPL",))
    assert type(port.inner).__name__ == "YahooDataAdapter"
    cn = data_port_for_symbols(("600519.SH",))
    assert type(cn.inner).__name__ == "AkShareDataAdapter"


def test_offline_flag_zero_stays_on_yahoo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHALOOP_OFFLINE_MARKET_DATA", "0")
    port = data_port_for_symbols(("AAPL",))
    assert type(port.inner).__name__ == "YahooDataAdapter"


def test_offline_flag_returns_local_bars_without_yahoo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHALOOP_OFFLINE_MARKET_DATA", "1")

    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("live Yahoo download must not run")

    import yfinance

    monkeypatch.setattr(yfinance, "download", explode)
    port = data_port_for_symbols(("AAPL", "600519.SH"))
    assert type(port.inner).__name__ == "OfflineMarketDataAdapter"
    frame = port.load_daily(("AAPL", "SPX"), date(2014, 1, 1), date(2024, 1, 1))
    assert list(frame.columns) == ["AAPL", "SPX"]
    assert len(frame) > 252 * 8
    assert bool(frame.notna().all().all())
    again = port.load_daily(("AAPL",), date(2014, 1, 1), date(2024, 1, 1))
    assert frame["AAPL"].equals(again["AAPL"])


def test_e2e_hold_defaults_off_and_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHALOOP_E2E_HOLD_RUNNING_SEC", raising=False)
    assert e2e_hold_running_seconds() == 0
    monkeypatch.setenv("ALPHALOOP_E2E_HOLD_RUNNING_SEC", "nope")
    assert e2e_hold_running_seconds() == 0
    monkeypatch.setenv("ALPHALOOP_E2E_HOLD_RUNNING_SEC", "12")
    assert e2e_hold_running_seconds() == 12
    monkeypatch.setenv("ALPHALOOP_E2E_HOLD_RUNNING_SEC", "999")
    assert e2e_hold_running_seconds() == 120
