from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from alphaloop.contracts.research_spec import ALLOWED_PROFILES
from alphaloop.engineer import (
    atr_breakout,
    bollinger_zscore,
    macd,
    momentum_12_1,
    obv_slope,
    ohlr_4_pct,
    parkinson_hist_vol,
    pairs_spread,
    roc,
    rsi,
)

DSL_SCHEMA_VERSION = "dsl.v1"

_FACTORS = {
    "rsi": rsi,
    "macd": macd,
    "roc": roc,
    "momentum_12_1": momentum_12_1,
    "bollinger_zscore": bollinger_zscore,
    "ohlr_4_pct": ohlr_4_pct,
    "pairs_spread": pairs_spread,
    "atr_breakout": atr_breakout,
    "parkinson_hist_vol": parkinson_hist_vol,
    "obv_slope": obv_slope,
}

ALLOWED_KINDS = tuple(_FACTORS)


class UnsupportedDslError(ValueError):
    """Raised when a strategy document cannot be interpreted."""


@dataclass(frozen=True)
class StrategyDocument:
    schema_version: str
    kind: str
    parameters: dict
    universe: tuple[str, ...]
    market_profile: str


def parse_strategy_document(payload: Mapping[str, Any]) -> StrategyDocument:
    schema = str(payload.get("schema_version", ""))
    if schema != DSL_SCHEMA_VERSION:
        raise UnsupportedDslError(f"unsupported DSL schema: {schema}")
    kind = str(payload.get("kind", ""))
    if kind not in _FACTORS:
        raise UnsupportedDslError(f"unsupported DSL kind: {kind}")
    universe_raw = payload.get("universe") or ()
    universe = tuple(str(item).strip() for item in universe_raw if str(item).strip())
    if not universe:
        raise UnsupportedDslError("universe must not be empty")
    profile = str(payload.get("market_profile", ""))
    if profile not in ALLOWED_PROFILES:
        raise UnsupportedDslError(f"unsupported market_profile: {profile}")
    parameters = dict(payload.get("parameters") or {})
    return StrategyDocument(
        schema_version=schema,
        kind=kind,
        parameters=parameters,
        universe=universe,
        market_profile=profile,
    )


def _asof_weight(series: pd.Series, effective_at: Any) -> float:
    if series.empty:
        return 0.0
    stamp = pd.Timestamp(effective_at)
    if stamp not in series.index:
        return 0.0
    value = float(series.loc[stamp])
    if value < 0.0 or not pd.notna(value):
        return 0.0
    return value


def _call_factor(
    kind: str,
    primary: pd.Series,
    prices: Mapping[str, pd.Series],
    parameters: Mapping[str, Any],
) -> pd.Series:
    fn = _FACTORS[kind]
    first_param = next(iter(inspect.signature(fn).parameters))
    kwargs = {
        key: value
        for key, value in parameters.items()
        if key in inspect.signature(fn).parameters and key != first_param
    }
    if kind == "pairs_spread":
        hedge = parameters.get("hedge_asset")
        if not hedge or hedge not in prices:
            raise UnsupportedDslError("pairs_spread requires parameters.hedge_asset in prices")
        kwargs.pop("hedge_asset", None)
        return fn(primary, prices[str(hedge)], **kwargs)
    if kind == "obv_slope":
        raise UnsupportedDslError("obv_slope requires a volume series")
    if kind in {"atr_breakout", "ohlr_4_pct"}:
        ohlc = pd.DataFrame({"high": primary, "low": primary, "close": primary})
        return fn(ohlc, **kwargs)
    return fn(primary, **kwargs)


def target_weights(
    doc: StrategyDocument,
    prices: Mapping[str, pd.Series],
    effective_at: Any,
) -> dict[str, float]:
    raw: dict[str, float] = {}
    for asset in doc.universe:
        series = prices.get(asset)
        if series is None or series.empty:
            raw[asset] = 0.0
            continue
        weights = _call_factor(doc.kind, series, prices, doc.parameters)
        raw[asset] = _asof_weight(weights, effective_at)
    total = sum(raw.values())
    if total <= 0.0:
        return {asset: 0.0 for asset in doc.universe}
    return {asset: value / total for asset, value in raw.items()}
