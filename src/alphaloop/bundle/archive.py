from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Mapping, Union

import yaml

from alphaloop.contracts.bundle import (
    BundleSchemaError,
    StrategyCandidateBundle,
    bundle_from_payload,
    canonical_hash,
)

ASB_SCHEMA_VERSION = "asb.v1"
FORBIDDEN_SUFFIXES = (
    ".py",
    ".pyc",
    ".pyo",
    ".so",
    ".dll",
    ".exe",
    ".sh",
    ".bat",
    ".whl",
    ".ipynb",
)

PathLike = Union[str, Path]


def _yaml_bytes(payload: object) -> bytes:
    return yaml.safe_dump(payload, sort_keys=True).encode("utf-8")


def _load_yaml(data: bytes) -> object:
    payload = yaml.safe_load(data.decode("utf-8"))
    return payload


def _reject_member_name(name: str) -> None:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or ".." in Path(normalized).parts:
        raise BundleSchemaError(f"illegal archive member: {name}")
    suffix = Path(normalized).suffix.lower()
    if suffix in FORBIDDEN_SUFFIXES:
        raise BundleSchemaError(f"executable member not allowed: {name}")


def inspect_asb(path: PathLike) -> tuple[str, ...]:
    with zipfile.ZipFile(Path(path), "r") as archive:
        names = tuple(archive.namelist())
    for name in names:
        _reject_member_name(name)
    return names


def write_asb(
    path: PathLike,
    bundle: StrategyCandidateBundle,
    *,
    evidence: Mapping[str, bytes],
    conformance: Mapping[str, bytes],
) -> None:
    members: dict[str, bytes] = {
        "bundle.yaml": _yaml_bytes(
            {
                "schema_version": bundle.schema_version,
                "bundle_id": bundle.bundle_id,
                "content_hash": bundle.content_hash,
                "registry_uri": bundle.registry_uri,
            }
        ),
        "strategy.dsl.yaml": _yaml_bytes(dict(bundle.strategy_dsl)),
        "market-profile.yaml": _yaml_bytes({"name": bundle.market_profile}),
        "parameters.yaml": _yaml_bytes(dict(bundle.parameters)),
        "risk-envelope.yaml": _yaml_bytes(dict(bundle.risk_envelope)),
        "lineage.yaml": _yaml_bytes(dict(bundle.lineage)),
        "conformance/inputs.yaml": _yaml_bytes(
            dict(bundle.conformance.get("inputs") or {})
        ),
        "conformance/expected_weights.yaml": _yaml_bytes(
            dict(bundle.conformance.get("expected_weights") or {})
        ),
    }
    for name, data in evidence.items():
        members[f"evidence/{Path(name).name}"] = data
    for name, data in conformance.items():
        members[f"conformance/{Path(name).name}"] = data
    for name in members:
        _reject_member_name(name)
    destination = Path(path)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(members.items()):
            archive.writestr(name, data)


def read_asb(path: PathLike) -> StrategyCandidateBundle:
    names = inspect_asb(path)
    with zipfile.ZipFile(Path(path), "r") as archive:
        files = {name: archive.read(name) for name in names}

    def _require(name: str) -> bytes:
        if name not in files:
            raise BundleSchemaError(f"missing archive member: {name}")
        return files[name]

    meta = _load_yaml(_require("bundle.yaml"))
    profile = _load_yaml(_require("market-profile.yaml"))
    if not isinstance(meta, dict) or not isinstance(profile, dict):
        raise BundleSchemaError("bundle metadata must be mappings")
    payload = {
        "schema_version": meta.get("schema_version"),
        "strategy_dsl": _load_yaml(_require("strategy.dsl.yaml")),
        "market_profile": profile.get("name"),
        "parameters": _load_yaml(_require("parameters.yaml")),
        "risk_envelope": _load_yaml(_require("risk-envelope.yaml")),
        "lineage": _load_yaml(_require("lineage.yaml")),
        "conformance": {
            "inputs": _load_yaml(_require("conformance/inputs.yaml")),
            "expected_weights": _load_yaml(_require("conformance/expected_weights.yaml")),
        },
        "registry_uri": meta.get("registry_uri"),
    }
    try:
        bundle = bundle_from_payload(payload)
    except (BundleSchemaError, KeyError, TypeError, ValueError) as exc:
        raise BundleSchemaError(str(exc)) from exc
    declared = meta.get("content_hash")
    if declared != bundle.content_hash or canonical_hash(bundle.to_payload()) != declared:
        raise BundleSchemaError("bundle content hash mismatch")
    if meta.get("bundle_id") not in (None, bundle.bundle_id):
        raise BundleSchemaError("bundle_id does not match content hash")
    return bundle
