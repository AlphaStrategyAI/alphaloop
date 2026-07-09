"""
openstrategy.live - Broker connectivity for paper and live trading.

This subpackage contains the Broker interface and concrete broker
adapters (currently Alpaca only).

HARD WALL
---------
Live trading is gated by TWO flags. See `broker.py` for details.

  1. `paper=False`
  2. `confirm_live=True`

If either is missing, `LiveTradingRefused` is raised at construction
time. There is no way to bypass this check from inside the package.

v1.0 scope
----------
  - AlpacaAdapter (paper-only by default)
  - Read-only API: get_account, is_market_open
  - No order placement (out of v1.0 scope)

Example
-------
    from openstrategy.live import AlpacaAdapter

    # Paper trading (default, no opt-in required)
    broker = AlpacaAdapter(api_key="PK...", secret="...")
    print(broker.is_paper)  # True

    # Live trading requires explicit confirmation
    broker = AlpacaAdapter(
        api_key="AK...",
        secret="...",
        paper=False,
        confirm_live=True,  # REQUIRED
    )
    print(broker.is_paper)  # False

    # Trying to go live without confirmation:
    broker = AlpacaAdapter(
        api_key="AK...",
        secret="...",
        paper=False,
        # confirm_live missing!
    )
    # -> LiveTradingRefused
"""
from .alpaca import LIVE_BASE_URL, PAPER_BASE_URL, AlpacaAdapter
from .broker import (
    CONFIRM_LIVE_FLAG,
    Broker,
    BrokerConfig,
    LiveTradingRefused,
)

__all__ = [
    # Broker interface
    "Broker",
    "BrokerConfig",
    "LiveTradingRefused",
    "CONFIRM_LIVE_FLAG",
    # Alpaca adapter
    "AlpacaAdapter",
    "PAPER_BASE_URL",
    "LIVE_BASE_URL",
]