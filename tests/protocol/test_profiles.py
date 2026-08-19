from __future__ import annotations

import pytest

from alphaloop.protocol.dsl import StrategyDocument
from alphaloop.protocol.profiles import (
    CRYPTO_DAILY,
    US_EQUITY_DAILY,
    MixedProfileError,
    assert_single_profile,
    get_profile,
)


def _doc(profile: str) -> StrategyDocument:
    return StrategyDocument(
        schema_version="dsl.v1",
        kind="momentum_12_1",
        parameters={},
        universe=("AAPL",),
        market_profile=profile,
    )


def test_us_equity_profile_constants():
    profile = get_profile("us-equity-daily")
    assert profile is US_EQUITY_DAILY
    assert profile.name == "us-equity-daily"
    assert profile.periods_per_year == 252
    assert profile.default_benchmark == "SPY"
    assert profile.cost_bps == 5.0
    assert profile.calendar == "nyse"


def test_crypto_profile_constants():
    profile = get_profile("crypto-daily")
    assert profile is CRYPTO_DAILY
    assert profile.name == "crypto-daily"
    assert profile.periods_per_year == 365
    assert profile.default_benchmark == "BTC-USD"
    assert profile.cost_bps == 10.0
    assert profile.calendar == "247"


def test_unknown_profile_rejected():
    with pytest.raises(ValueError):
        get_profile("fx-hourly")


def test_mixed_profiles_rejected():
    with pytest.raises(MixedProfileError):
        assert_single_profile((_doc("us-equity-daily"), _doc("crypto-daily")))


def test_single_profile_ok():
    assert_single_profile((_doc("us-equity-daily"), _doc("us-equity-daily")))
