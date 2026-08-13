"""
Tests for the Broker protocol and BrokerConfig dataclass.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from alphaloop.live import (  # noqa: E402
    Broker,
    BrokerConfig,
    CONFIRM_LIVE_FLAG,
    LiveTradingRefused,
)
from alphaloop.live.broker import _enforce_safety  # noqa: E402


# --- BrokerConfig dataclass ---


def test_broker_config_defaults():
    c = BrokerConfig()
    assert c.paper is True
    assert c.confirm_live is False
    assert c.api_key is None
    assert c.secret is None
    assert c.base_url is None
    assert c.timeout_seconds == 30.0


def test_broker_config_accepts_all_fields():
    c = BrokerConfig(
        paper=False,
        confirm_live=True,
        api_key="AK",
        secret="SEC",
        base_url="https://example.com",
        timeout_seconds=10.0,
    )
    assert c.paper is False
    assert c.confirm_live is True
    assert c.api_key == "AK"
    assert c.base_url == "https://example.com"
    assert c.timeout_seconds == 10.0


# --- _enforce_safety ---


def test_enforce_safety_paper_never_raises():
    """paper=True always passes, regardless of confirm_live."""
    _enforce_safety(BrokerConfig(paper=True, confirm_live=False))
    _enforce_safety(BrokerConfig(paper=True, confirm_live=True))


def test_enforce_safety_live_without_confirm_raises():
    with pytest.raises(LiveTradingRefused):
        _enforce_safety(BrokerConfig(paper=False, confirm_live=False))


def test_enforce_safety_live_with_confirm_passes():
    _enforce_safety(BrokerConfig(paper=False, confirm_live=True))


def test_enforce_safety_error_message_includes_flag_name():
    with pytest.raises(LiveTradingRefused) as exc:
        _enforce_safety(BrokerConfig(paper=False, confirm_live=False))
    assert CONFIRM_LIVE_FLAG in str(exc.value)


# --- Broker protocol (runtime_checkable) ---


def test_alpaca_adapter_is_broker():
    """AlpacaAdapter should satisfy the Broker protocol."""
    from alphaloop.live import AlpacaAdapter
    b = AlpacaAdapter()
    assert isinstance(b, Broker)


def test_broker_protocol_required_methods():
    """The Broker protocol requires is_paper, name, get_account, is_market_open."""
    required = {"is_paper", "name", "get_account", "is_market_open"}
    for attr in required:
        assert hasattr(Broker, attr)


# --- Constants ---


def test_confirm_live_flag_is_string():
    assert isinstance(CONFIRM_LIVE_FLAG, str)
    assert len(CONFIRM_LIVE_FLAG) > 10  # Hard to type by accident


def test_live_trading_refused_is_exception():
    """LiveTradingRefused must be an Exception subclass so callers
    can catch it with `except Exception`."""
    assert issubclass(LiveTradingRefused, Exception)


# --- Configuration safety invariants ---


def test_paper_default_in_broker_config():
    """Even BrokerConfig() should default to paper=True."""
    assert BrokerConfig().paper is True


def test_default_does_not_bypass_safety():
    """Constructing BrokerConfig() must be safe."""
    cfg = BrokerConfig()
    # No raise for paper=True
    _enforce_safety(cfg)