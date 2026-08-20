from __future__ import annotations

import pandas as pd
import pytest

from alphaloop.protocol.dsl import (
    ALLOWED_KINDS,
    DIRECTIONAL_SIGNAL_KINDS,
    DSL_SCHEMA_VERSION,
    FEATURE_KINDS,
    VOLUME_KINDS,
    StrategyDocument,
    UnsupportedDslError,
    parse_strategy_document,
    target_weights,
)


def _rising_prices(n: int = 300) -> pd.Series:
    idx = pd.bdate_range("2018-01-01", periods=n)
    return pd.Series([100.0 + i for i in range(n)], index=idx, dtype=float)


def _payload(**overrides):
    body = {
        "schema_version": DSL_SCHEMA_VERSION,
        "kind": "momentum_12_1",
        "parameters": {},
        "universe": ["AAPL", "MSFT"],
        "market_profile": "us-equity-daily",
    }
    body.update(overrides)
    return body


def test_parse_strategy_document_round_trip():
    doc = parse_strategy_document(_payload())
    assert isinstance(doc, StrategyDocument)
    assert doc.kind == "momentum_12_1"
    assert doc.universe == ("AAPL", "MSFT")
    assert doc.schema_version == DSL_SCHEMA_VERSION


def test_unknown_kind_rejected():
    with pytest.raises(UnsupportedDslError):
        parse_strategy_document(_payload(kind="MovingAverageCrossoverStrategy"))


def test_empty_universe_rejected():
    with pytest.raises(UnsupportedDslError):
        parse_strategy_document(_payload(universe=[]))


def test_wrong_schema_rejected():
    with pytest.raises(UnsupportedDslError):
        parse_strategy_document(_payload(schema_version="dsl.v0"))


def test_allowed_kinds_are_engineer_factors():
    assert "momentum_12_1" in ALLOWED_KINDS
    assert "rsi" in ALLOWED_KINDS
    assert len(ALLOWED_KINDS) == 10


def test_directional_signal_kinds_exclude_feature_and_volume():
    assert FEATURE_KINDS == ("parkinson_hist_vol",)
    assert VOLUME_KINDS == ("obv_slope",)
    assert "parkinson_hist_vol" in ALLOWED_KINDS
    assert "obv_slope" in ALLOWED_KINDS
    assert "parkinson_hist_vol" not in DIRECTIONAL_SIGNAL_KINDS
    assert "obv_slope" not in DIRECTIONAL_SIGNAL_KINDS
    assert len(DIRECTIONAL_SIGNAL_KINDS) == 8
    assert DIRECTIONAL_SIGNAL_KINDS == tuple(
        kind
        for kind in ALLOWED_KINDS
        if kind not in FEATURE_KINDS and kind not in VOLUME_KINDS
    )


def test_momentum_weights_sum_to_one_on_rising_series():
    doc = parse_strategy_document(_payload())
    prices = _rising_prices()
    at = prices.index[-1]
    weights = target_weights(doc, {"AAPL": prices, "MSFT": prices}, at)
    assert set(weights) == {"AAPL", "MSFT"}
    assert all(w >= 0.0 for w in weights.values())
    assert pytest.approx(sum(weights.values()), abs=1e-9) == 1.0


def test_missing_bar_yields_zero_for_that_asset():
    doc = parse_strategy_document(_payload(kind="rsi", universe=["AAPL", "MSFT"]))
    aapl = _rising_prices(40)
    msft = _rising_prices(40).iloc[:-10]
    weights = target_weights(doc, {"AAPL": aapl, "MSFT": msft}, aapl.index[-1])
    assert weights["MSFT"] == 0.0
    assert weights["AAPL"] >= 0.0


def test_ohlr_close_only_target_weights_do_not_raise():
    doc = parse_strategy_document(_payload(kind="ohlr_4_pct", universe=["AAPL"]))
    prices = _rising_prices(40)
    weights = target_weights(doc, {"AAPL": prices}, prices.index[-1])
    assert weights["AAPL"] >= 0.0


def test_pairs_default_hedge_from_universe():
    doc = parse_strategy_document(_payload(kind="pairs_spread", universe=["AAPL", "MSFT"]))
    aapl = _rising_prices(80)
    msft = _rising_prices(80) * 1.01
    weights = target_weights(doc, {"AAPL": aapl, "MSFT": msft}, aapl.index[-1])
    assert set(weights) == {"AAPL", "MSFT"}
    assert all(w >= 0.0 for w in weights.values())


def test_pairs_single_name_universe_still_requires_hedge():
    doc = parse_strategy_document(_payload(kind="pairs_spread", universe=["AAPL"]))
    prices = _rising_prices(80)
    with pytest.raises(UnsupportedDslError):
        target_weights(doc, {"AAPL": prices}, prices.index[-1])
