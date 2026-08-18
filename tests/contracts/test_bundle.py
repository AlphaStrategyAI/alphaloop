from __future__ import annotations

import pytest

from alphaloop.contracts.bundle import (
    ExportNotAllowed,
    assert_exportable,
    bundle_from_payload,
    canonical_hash,
)
from alphaloop.contracts.status import ResearchOutcome


def _payload() -> dict:
    return {
        "schema_version": "1",
        "strategy_dsl": {"kind": "momentum_12_1", "lookback": 252},
        "market_profile": "us-equity-daily",
        "parameters": {"lookback": 252},
        "risk_envelope": {"max_weight": 0.05},
        "lineage": {"run_id": "r1", "candidate_id": "c1"},
        "conformance": {
            "inputs": {"as_of": "2024-01-02"},
            "expected_weights": {"AAPL": 0.01, "MSFT": 0.02},
        },
        "registry_uri": None,
    }


def test_hash_is_order_independent():
    a = canonical_hash(_payload())
    flipped = dict(reversed(list(_payload().items())))
    assert canonical_hash(flipped) == a


def test_bundle_id_is_derived_from_hash():
    bundle = bundle_from_payload(_payload())
    digest = canonical_hash(_payload())
    assert bundle.content_hash == digest
    assert bundle.bundle_id == "b_" + digest[:32]
    assert bundle.registry_uri is None


def test_export_requires_found_and_known_candidate():
    assert_exportable(ResearchOutcome.FOUND, ("c1",), "c1")
    with pytest.raises(ExportNotAllowed):
        assert_exportable(ResearchOutcome.NO_EVIDENCE, ("c1",), "c1")
    with pytest.raises(ExportNotAllowed):
        assert_exportable(ResearchOutcome.FOUND, ("c1",), "c2")


def test_registry_uri_normalization_produces_same_hash():
    base = _payload()
    omitted = {k: v for k, v in base.items() if k != "registry_uri"}
    empty = {**base, "registry_uri": ""}
    a = canonical_hash(base)
    b = canonical_hash(omitted)
    c = canonical_hash(empty)
    assert a == b == c
    assert bundle_from_payload(base).bundle_id == bundle_from_payload(omitted).bundle_id


def test_to_payload_recomputes_hash():
    bundle = bundle_from_payload(_payload())
    assert canonical_hash(bundle.to_payload()) == bundle.content_hash
