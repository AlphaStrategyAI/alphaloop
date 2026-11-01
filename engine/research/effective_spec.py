"""Full effective definition inherited by each new research version."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from engine.research.families import LEGACY_FAMILY_METHOD, LEGACY_STRATEGY_FAMILY
from engine.research.models import Research

SPEC_FIELDS = (
    "max_drawdown_floor",
    "model_family",
    "lookback_days",
    "entry_z",
    "side",
    "strategy_family",
    "family_method",
    "primary_factor",
    "cost_model",
)

DEFAULT_EFFECTIVE_SPEC: dict[str, Any] = {
    "max_drawdown_floor": -0.25,
    "model_family": "mean_reversion",
    "lookback_days": 20,
    "entry_z": 1.0,
    "side": "long_only",
    "strategy_family": LEGACY_STRATEGY_FAMILY,
    "family_method": LEGACY_FAMILY_METHOD,
    "primary_factor": None,
    "cost_model": "legacy_zero",
}


def digest_spec(spec: dict[str, Any]) -> str:
    encoded = json.dumps(spec, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _parent_spec(research: Research) -> dict[str, Any] | None:
    if not research.versions:
        return None
    previous = research.versions[-1]
    if previous.effective_spec_snapshot:
        return dict(previous.effective_spec_snapshot)
    if previous.rounds:
        spec = previous.rounds[-1].accepted_attempt.spec
        if spec is None:
            return None
        return {
            "max_drawdown_floor": spec.max_drawdown_floor,
            "model_family": spec.model_family,
            "lookback_days": spec.lookback_days,
            "entry_z": spec.entry_z,
            "side": spec.side,
            "strategy_family": spec.strategy_family,
            "family_method": spec.family_method,
            "primary_factor": spec.primary_factor,
            "cost_model": spec.cost_model,
        }
    return None


def inherit_effective_spec(
    research: Research,
    changes: tuple[tuple[str, object], ...],
) -> tuple[dict[str, Any], str | None]:
    """Copy the parent definition and apply only this approval's typed fields."""
    parent = _parent_spec(research)
    parent_digest = digest_spec(parent) if parent else None
    spec = dict(parent or DEFAULT_EFFECTIVE_SPEC)
    for field_name, value in changes:
        if field_name in SPEC_FIELDS:
            spec[field_name] = _jsonable(value)
    return spec, parent_digest


def inherited_drawdown_floor(research: Research, prior_floor: float | None) -> float:
    if prior_floor is not None:
        return prior_floor
    if research.current_version_number and research.versions:
        version = research.versions[research.current_version_number - 1]
        snapshot = version.effective_spec_snapshot or {}
        raw = snapshot.get("max_drawdown_floor")
        if isinstance(raw, (int, float)):
            return float(raw)
    return -0.25
