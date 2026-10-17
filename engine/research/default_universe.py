"""Static default symbol pools — pending product sign-off (see acceptance report)."""

from __future__ import annotations

from engine.research.models import AssetClass, Market

PROPOSAL_DATE = "2026-10-17"
PROPOSAL_NOTE = "pending product sign-off"

# US broad ETFs + liquid large caps (Yahoo daily); proposal as of PROPOSAL_DATE.
US_EQUITY_DEFAULT: tuple[str, ...] = (
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
)


def default_universe_symbols(
    market: Market,
    asset_class: AssetClass,
    underlying: AssetClass,
) -> tuple[str, ...]:
    if market is Market.US and asset_class is AssetClass.EQUITY and underlying is AssetClass.EQUITY:
        return US_EQUITY_DEFAULT
    return ()
