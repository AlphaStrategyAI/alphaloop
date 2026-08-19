from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
import yaml

from alphaloop.contracts.bundle import BundleSchemaError, bundle_from_payload, canonical_hash


def _payload() -> dict:
    return {
        "schema_version": "asb.v1",
        "strategy_dsl": {
            "schema_version": "dsl.v1",
            "kind": "momentum_12_1",
            "parameters": {},
            "universe": ["AAPL", "MSFT"],
            "market_profile": "us-equity-daily",
        },
        "market_profile": "us-equity-daily",
        "parameters": {},
        "risk_envelope": {"max_weight": 1.0},
        "lineage": {"run_id": "j_1", "candidate_id": "c_1"},
        "conformance": {
            "inputs": {"as_of": "2018-12-31"},
            "expected_weights": {"AAPL": 0.5, "MSFT": 0.5},
        },
        "registry_uri": None,
    }


def test_asb_round_trip_preserves_hash(tmp_path):
    from alphaloop.bundle.archive import inspect_asb, read_asb, write_asb

    bundle = bundle_from_payload(_payload())
    path = tmp_path / "strategy.asb"
    write_asb(
        path,
        bundle,
        evidence={"gates.json": b"{}"},
        conformance={
            "inputs.yaml": yaml.safe_dump(dict(bundle.conformance["inputs"])).encode(),
            "expected_weights.yaml": yaml.safe_dump(
                dict(bundle.conformance["expected_weights"])
            ).encode(),
        },
    )
    names = inspect_asb(path)
    assert "bundle.yaml" in names
    assert "strategy.dsl.yaml" in names
    assert "evidence/gates.json" in names
    assert not any(name.endswith(".py") for name in names)
    loaded = read_asb(path)
    assert loaded.content_hash == bundle.content_hash
    assert loaded.bundle_id == bundle.bundle_id
    assert canonical_hash(loaded.to_payload()) == bundle.content_hash


def test_write_rejects_python_member(tmp_path):
    from alphaloop.bundle.archive import write_asb

    bundle = bundle_from_payload(_payload())
    with pytest.raises(BundleSchemaError):
        write_asb(
            tmp_path / "bad.asb",
            bundle,
            evidence={"strategy.py": b"print(1)\n"},
            conformance={},
        )


def test_read_rejects_python_member(tmp_path):
    from alphaloop.bundle.archive import read_asb

    path = tmp_path / "evil.asb"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("bundle.yaml", "schema_version: asb.v1\n")
        zf.writestr("payload.py", "x = 1\n")
    with pytest.raises(BundleSchemaError):
        read_asb(path)


def test_read_rejects_hash_mismatch(tmp_path):
    from alphaloop.bundle.archive import read_asb, write_asb

    bundle = bundle_from_payload(_payload())
    path = tmp_path / "strategy.asb"
    write_asb(path, bundle, evidence={}, conformance={})
    mutated = tmp_path / "mutated.asb"
    with zipfile.ZipFile(path, "r") as src, zipfile.ZipFile(mutated, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "parameters.yaml":
                data = b"lookback: 999\n"
            dst.writestr(item.filename, data)
    with pytest.raises(BundleSchemaError):
        read_asb(mutated)


def test_conformance_fixture_weights_are_yaml_not_python():
    from alphaloop.bundle.fixtures import (
        CONFORMANCE_AS_OF,
        conformance_members,
        conformance_prices,
        expected_weights,
    )

    prices = conformance_prices()
    weights = expected_weights(
        "momentum_12_1",
        {},
        ("AAPL", "MSFT"),
        "us-equity-daily",
        prices,
        CONFORMANCE_AS_OF,
    )
    total = sum(weights.values())
    assert total == 0.0 or abs(total - 1.0) < 1e-9
    members = conformance_members(
        "momentum_12_1",
        {},
        ("AAPL", "MSFT"),
        "us-equity-daily",
    )
    assert "inputs.yaml" in members
    assert "expected_weights.yaml" in members
    for name, data in members.items():
        assert not name.endswith(".py")
        text = data.decode("utf-8")
        assert "def " not in text
        yaml.safe_load(text)
