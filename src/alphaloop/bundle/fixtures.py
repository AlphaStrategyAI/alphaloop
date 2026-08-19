from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd
import yaml

from alphaloop.protocol.dsl import DSL_SCHEMA_VERSION, parse_strategy_document, target_weights

CONFORMANCE_AS_OF = pd.Timestamp("2018-12-31")


def conformance_prices() -> dict[str, pd.Series]:
    idx = pd.bdate_range("2018-01-01", periods=300)
    series = pd.Series([100.0 + i for i in range(300)], index=idx, dtype=float)
    return {"AAPL": series, "MSFT": series}


def expected_weights(
    kind: str,
    parameters: Mapping[str, Any],
    universe: Sequence[str],
    profile: str,
    prices: Mapping[str, pd.Series],
    as_of: Any,
) -> dict[str, float]:
    doc = parse_strategy_document(
        {
            "schema_version": DSL_SCHEMA_VERSION,
            "kind": kind,
            "parameters": dict(parameters),
            "universe": list(universe),
            "market_profile": profile,
        }
    )
    return target_weights(doc, prices, as_of)


def conformance_members(
    kind: str,
    parameters: Mapping[str, Any],
    universe: Sequence[str],
    profile: str,
) -> dict[str, bytes]:
    prices = conformance_prices()
    weights = expected_weights(
        kind, parameters, universe, profile, prices, CONFORMANCE_AS_OF
    )
    inputs = {
        "as_of": CONFORMANCE_AS_OF.isoformat(),
        "universe": list(universe),
    }
    return {
        "inputs.yaml": yaml.safe_dump(inputs, sort_keys=True).encode("utf-8"),
        "expected_weights.yaml": yaml.safe_dump(weights, sort_keys=True).encode("utf-8"),
    }
