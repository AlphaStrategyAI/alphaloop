from __future__ import annotations

from typing import Sequence

from alphaloop.protocol.dsl import StrategyDocument
from alphaloop.protocol.profiles.crypto_daily import CRYPTO_DAILY
from alphaloop.protocol.profiles.us_equity_daily import US_EQUITY_DAILY, MarketProfile

_PROFILES = {
    US_EQUITY_DAILY.name: US_EQUITY_DAILY,
    CRYPTO_DAILY.name: CRYPTO_DAILY,
}


class MixedProfileError(ValueError):
    """Raised when candidates from different market profiles are ranked together."""


def get_profile(name: str) -> MarketProfile:
    try:
        return _PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unsupported market profile: {name}") from exc


def assert_single_profile(docs: Sequence[StrategyDocument]) -> None:
    names = {doc.market_profile for doc in docs}
    if len(names) > 1:
        raise MixedProfileError("candidates from different market profiles cannot be ranked together")


__all__ = [
    "CRYPTO_DAILY",
    "MarketProfile",
    "MixedProfileError",
    "US_EQUITY_DAILY",
    "assert_single_profile",
    "get_profile",
]
