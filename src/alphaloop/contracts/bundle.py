from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from .status import ResearchOutcome


class ExportNotAllowed(ValueError):
    """Raised when a candidate cannot be exported as a bundle."""


class BundleSchemaError(ValueError):
    """Raised when a bundle payload contains disallowed fields."""


_BUNDLE_HASH_FIELDS = (
    "schema_version",
    "strategy_dsl",
    "market_profile",
    "parameters",
    "risk_envelope",
    "lineage",
    "conformance",
    "registry_uri",
)
_ALLOWED_PAYLOAD_KEYS = frozenset(_BUNDLE_HASH_FIELDS)
_IDENTITY_KEYS = frozenset({"bundle_id", "content_hash"})


def _reject_unknown_keys(payload: Mapping[str, Any]) -> None:
    extra = set(payload) - _ALLOWED_PAYLOAD_KEYS - _IDENTITY_KEYS
    if extra:
        raise BundleSchemaError(
            "bundle payload contains disallowed fields "
            f"{sorted(extra)}; candidate bundles are YAML/DSL data only"
        )


def _normalize_registry_uri(registry: Any) -> Optional[str]:
    if registry in (None, ""):
        return None
    return str(registry)


def bundle_hash_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    _reject_unknown_keys(payload)
    return {
        "schema_version": str(payload["schema_version"]),
        "strategy_dsl": dict(payload["strategy_dsl"]),
        "market_profile": str(payload["market_profile"]),
        "parameters": dict(payload["parameters"]),
        "risk_envelope": dict(payload["risk_envelope"]),
        "lineage": dict(payload["lineage"]),
        "conformance": dict(payload["conformance"]),
        "registry_uri": _normalize_registry_uri(payload.get("registry_uri")),
    }


def canonical_hash(payload: Mapping[str, Any]) -> str:
    projection = bundle_hash_projection(payload)
    encoded = json.dumps(projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class StrategyCandidateBundle:
    schema_version: str
    bundle_id: str
    content_hash: str
    strategy_dsl: dict
    market_profile: str
    parameters: dict
    risk_envelope: dict
    lineage: dict
    conformance: dict
    registry_uri: Optional[str]

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "strategy_dsl": dict(self.strategy_dsl),
            "market_profile": self.market_profile,
            "parameters": dict(self.parameters),
            "risk_envelope": dict(self.risk_envelope),
            "lineage": dict(self.lineage),
            "conformance": dict(self.conformance),
            "registry_uri": self.registry_uri,
        }


def bundle_from_payload(payload: Mapping[str, Any]) -> StrategyCandidateBundle:
    projection = bundle_hash_projection(payload)
    digest = canonical_hash(projection)
    return StrategyCandidateBundle(
        schema_version=projection["schema_version"],
        bundle_id="b_" + digest[:32],
        content_hash=digest,
        strategy_dsl=projection["strategy_dsl"],
        market_profile=projection["market_profile"],
        parameters=projection["parameters"],
        risk_envelope=projection["risk_envelope"],
        lineage=projection["lineage"],
        conformance=projection["conformance"],
        registry_uri=projection["registry_uri"],
    )


def assert_exportable(
    outcome: ResearchOutcome,
    candidate_ids: Sequence[str],
    candidate_id: str,
) -> None:
    if outcome is not ResearchOutcome.FOUND:
        raise ExportNotAllowed("export requires research outcome FOUND")
    if candidate_id not in set(candidate_ids):
        raise ExportNotAllowed(f"candidate not in sealed evidence: {candidate_id}")
