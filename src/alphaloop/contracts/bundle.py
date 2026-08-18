from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from .status import ResearchOutcome


class ExportNotAllowed(ValueError):
    """Raised when a candidate cannot be exported as a bundle."""


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


def canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bundle_from_payload(payload: Mapping[str, Any]) -> StrategyCandidateBundle:
    digest = canonical_hash(payload)
    registry = payload.get("registry_uri")
    return StrategyCandidateBundle(
        schema_version=str(payload["schema_version"]),
        bundle_id="b_" + digest[:32],
        content_hash=digest,
        strategy_dsl=dict(payload["strategy_dsl"]),
        market_profile=str(payload["market_profile"]),
        parameters=dict(payload["parameters"]),
        risk_envelope=dict(payload["risk_envelope"]),
        lineage=dict(payload["lineage"]),
        conformance=dict(payload["conformance"]),
        registry_uri=None if registry in (None, "") else str(registry),
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
