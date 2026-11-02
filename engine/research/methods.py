from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from engine.research.display_names import method_label
from engine.research.models import (
    MethodDefinition,
    MethodRef,
    MethodSource,
    MethodUsage,
    Research,
)
from engine.verifiers import PIT_REVISION_V2, PIT_SCOPE, PIT_VERIFIER_REVISION, VERIFIER_REVISIONS


class ScorecardDimensionKind(StrEnum):
    """Scorecard dimension kinds (B6)."""
    PREDICTIVE_POWER = "predictive_power"
    STABILITY = "stability"
    PIT_CONSISTENCY = "pit_consistency"
    COST_SENSITIVITY = "cost_sensitivity"
    CROWDING = "crowding"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class ScorecardDimension:
    """Scorecard dimension with immutable semantics (B6)."""
    kind: ScorecardDimensionKind
    name: str
    description: str
    pass_threshold: float
    comparison: str
    failure_display: str
    unit: str | None = None


class DimensionSemanticChangeError(Exception):
    """Raised when attempting to change the semantic meaning of an existing dimension."""


def validate_dimension_immutability(
    old_dims: tuple[ScorecardDimension, ...],
    new_dims: tuple[ScorecardDimension, ...],
) -> None:
    """Validate that existing dimension semantics are not changed (B6 immutability rule).
    
    Adding new dimensions is allowed.
    Changing description, pass_threshold, comparison, or failure_display of existing
    dimensions by kind+name is not allowed - requires a new revision.
    Unit is not a semantic field and can be changed.
    """
    old_by_key = {(d.kind, d.name): d for d in old_dims}
    for new_dim in new_dims:
        key = (new_dim.kind, new_dim.name)
        if key in old_by_key:
            old_dim = old_by_key[key]
            if (
                old_dim.description != new_dim.description
                or old_dim.pass_threshold != new_dim.pass_threshold
                or old_dim.comparison != new_dim.comparison
                or old_dim.failure_display != new_dim.failure_display
            ):
                raise DimensionSemanticChangeError(
                    f"Cannot change semantic of existing dimension {key}. "
                    f"Create a new revision instead. "
                    f"Old: {old_dim}, New: {new_dim}"
                )

if TYPE_CHECKING:
    from engine.research.store import SQLiteStore

PRESET_IDS = (
    "scorecard.market",
    "overfit.walk",
    "stability.oos",
    "crowding.load",
    "cost.turnover",
    "pit.consistency",
)
PRESET_NAMES = {method_id: method_label(method_id) for method_id in PRESET_IDS}


def format_verifier_display(verifier_id: str) -> str:
    return method_label(verifier_id)


def format_verifier_ids(verifier_ids: tuple[str, ...]) -> tuple[str, ...]:
    deduped = tuple(dict.fromkeys(verifier_ids))
    return tuple(format_verifier_display(item) for item in deduped)


def _revision_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def create_method(
    store: SQLiteStore,
    method_id: str,
    name: str,
    description: str,
    body: str,
    source: MethodSource,
    now: datetime,
    deposited_from_research_id: str | None = None,
    supersedes: str | None = None,
) -> MethodDefinition:
    if method_is_executable_body(body):
        assert_golden_samples(body)
    definition = MethodDefinition(
        method_id=method_id,
        revision_hash=_revision_hash(body),
        name=name,
        description=description,
        body=body,
        source=source,
        deposited_from_research_id=deposited_from_research_id,
        created_at=now,
        supersedes=supersedes,
    )
    store.insert_method_definition(definition)
    return definition


def revise_method(
    store: SQLiteStore,
    method_id: str,
    name: str,
    description: str,
    body: str,
    now: datetime,
) -> MethodDefinition:
    current = store.latest_method_definition(method_id)
    if current is None:
        raise KeyError(method_id)
    return create_method(
        store,
        method_id,
        name,
        description,
        body,
        current.source,
        now,
        deposited_from_research_id=current.deposited_from_research_id,
        supersedes=current.revision_hash,
    )


def deposit_method(
    store: SQLiteStore,
    research_id: str,
    method_id: str,
    name: str,
    description: str,
    body: str,
    now: datetime,
) -> MethodDefinition:
    return create_method(
        store,
        method_id,
        name,
        description,
        body,
        MethodSource.DEPOSITED,
        now,
        deposited_from_research_id=research_id,
    )


def list_method_usage(store: SQLiteStore, method_id: str) -> tuple[MethodUsage, ...]:
    return store.list_method_usage(method_id)


def record_method_usage(
    store: SQLiteStore,
    research_id: str,
    version_number: int,
    method_set: tuple[MethodRef, ...],
) -> None:
    store.record_method_usage(research_id, version_number, method_set)


def record_verification_execution(
    store: SQLiteStore,
    research_id: str,
    version_number: int,
    verification: object | None,
) -> None:
    """Count researches that executed each verifier (pass or fail)."""
    if verification is None:
        return
    results = getattr(verification, "results", ())
    refs = tuple(
        MethodRef(item.verifier_id, item.revision)
        for item in results
    )
    if refs:
        record_method_usage(store, research_id, version_number, refs)


def distinct_research_usage_count(store: SQLiteStore, method_id: str) -> int:
    return len({row.research_id for row in list_method_usage(store, method_id)})


def _as_meta(meta: object) -> dict[str, object]:
    if not isinstance(meta, dict):
        raise TypeError(f"preset meta must be a dict, got {type(meta).__name__}")
    copied: dict[str, object] = {}
    for key, value in meta.items():
        copied[str(key)] = value
    return copied


def _builtin_preset_catalog() -> tuple[tuple[str, dict[str, object]], ...]:
    catalog: list[tuple[str, dict[str, object]]] = []
    for method_id, meta in VERIFIER_REVISIONS.items():
        catalog.append((method_id, _as_meta(meta)))
    for method_id, pit_meta in PIT_VERIFIER_REVISION.items():
        catalog.append((method_id, _as_meta(pit_meta)))
    pit_v2 = _as_meta(PIT_VERIFIER_REVISION["pit.consistency"])
    pit_v2["revision"] = PIT_REVISION_V2
    pit_v2["scope"] = PIT_SCOPE
    pit_v2["supersedes"] = "pit-v1"
    catalog.append(("pit.consistency", pit_v2))
    return tuple(catalog)


def iter_preset_definitions() -> tuple[tuple[str, dict[str, object]], ...]:
    """Preset rows keyed by (method id, revision). New revisions are additive."""
    return _builtin_preset_catalog()


def _insert_preset_if_missing(
    store: SQLiteStore,
    method_id: str,
    meta: dict[str, object],
    created_at: datetime,
) -> None:
    revision = str(meta["revision"])
    if store.get_method_definition(method_id, revision) is not None:
        return
    stored = dict(meta)
    supersedes_raw = stored.pop("supersedes", None)
    body = json.dumps(stored, sort_keys=True)
    supersedes = str(supersedes_raw) if supersedes_raw else None
    store.insert_method_definition(
        MethodDefinition(
            method_id=method_id,
            revision_hash=revision,
            name=PRESET_NAMES[method_id],
            description=body,
            body=body,
            source=MethodSource.PRESET,
            deposited_from_research_id=None,
            created_at=created_at,
            supersedes=supersedes,
        )
    )


def seed_preset_methods(store: SQLiteStore, now: datetime | None = None) -> None:
    created_at = now or datetime(2026, 1, 1, tzinfo=UTC)
    for method_id, meta in iter_preset_definitions():
        _insert_preset_if_missing(store, method_id, dict(meta), created_at)


def _method_payload(value: object) -> tuple[str, str, str, str] | None:
    if isinstance(value, MethodDefinition):
        return (value.method_id, value.name, value.description, value.body)
    if isinstance(value, dict) and "method_id" in value and "body" in value:
        method_id = str(value["method_id"])
        return (
            method_id,
            str(value.get("name") or method_id),
            str(value.get("description") or ""),
            str(value["body"]),
        )
    return None


def as_method_refs(value: object) -> tuple[MethodRef, ...]:
    if not isinstance(value, (tuple, list)):
        return ()
    refs: list[MethodRef] = []
    for item in value:
        if isinstance(item, MethodRef):
            refs.append(item)
        elif isinstance(item, MethodDefinition):
            refs.append(MethodRef(item.method_id, item.revision_hash))
        elif isinstance(item, dict) and "method_id" in item:
            refs.append(
                MethodRef(str(item["method_id"]), str(item.get("revision_hash") or ""))
            )
    return tuple(refs)


def method_body_payload(body: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def method_is_executable_body(body: str) -> bool:
    payload = method_body_payload(body)
    return bool(payload and payload.get("executable") is True)


def method_is_executable(definition: MethodDefinition) -> bool:
    if definition.source is MethodSource.PRESET:
        return True
    return method_is_executable_body(definition.body)


def _threshold_passes(payload: dict[str, Any], observed: float) -> bool:
    threshold = float(payload["threshold"])
    comparison = str(payload.get("comparison", ">="))
    if comparison == ">=":
        return observed >= threshold
    if comparison == "<=":
        return observed <= threshold
    raise ValueError(f"unsupported comparison {comparison}")


def assert_golden_samples(body: str) -> None:
    """Freeze an executable operator only after a pass sample and a fail sample."""
    payload = method_body_payload(body)
    if payload is None:
        raise ValueError("executable method requires golden pass and fail samples")
    samples = payload.get("samples")
    if not isinstance(samples, list) or len(samples) < 2:
        raise ValueError("executable method requires golden pass and fail samples")
    saw_pass = False
    saw_fail = False
    for sample in samples:
        if not isinstance(sample, dict):
            raise TypeError("golden sample mismatch")
        expect = bool(sample.get("expect_pass"))
        raw_input = sample.get("input")
        if not isinstance(raw_input, dict) or "value" not in raw_input:
            raise ValueError("golden sample mismatch")
        actual = _threshold_passes(payload, float(raw_input["value"]))
        if actual != expect:
            raise ValueError("golden sample mismatch")
        saw_pass = saw_pass or expect
        saw_fail = saw_fail or not expect
    if not (saw_pass and saw_fail):
        raise ValueError("executable method requires both a passing and a failing golden sample")


def execute_method_revision(
    store: SQLiteStore,
    method_id: str,
    revision: str,
    observed: float,
) -> bool:
    definition = store.get_method_definition(method_id, revision)
    if definition is None:
        raise ValueError("unregistered method revision")
    if not method_is_executable(definition):
        raise ValueError("unimplemented method cannot be executed or counted as passed")
    payload = method_body_payload(definition.body)
    if payload is None or "threshold" not in payload:
        raise ValueError("unregistered method revision")
    return _threshold_passes(payload, float(observed))


def suggest_method_refs(
    store: SQLiteStore,
    query: str = "",
) -> tuple[tuple[MethodRef, ...], tuple[str, ...]]:
    """Executable MethodRefs, then unimplemented suggestions that cannot pass."""
    needle = query.strip().lower()
    executable: list[MethodRef] = []
    suggestions: list[str] = []
    for item in store.list_method_definitions():
        haystack = f"{item.method_id} {item.name}".lower()
        if needle and needle not in haystack:
            continue
        if method_is_executable(item):
            executable.append(MethodRef(item.method_id, item.revision_hash))
        else:
            suggestions.append(item.method_id)
    return tuple(executable), tuple(suggestions)


def deposit_confirmed_methods(store: SQLiteStore, research: Research, now: datetime) -> None:
    pending = research.pending_confirm
    if pending is None:
        return
    for field, value in pending.patch:
        if field in {"round1_methods", "method_set"}:
            items = value if isinstance(value, (tuple, list)) else ()
            for item in items:
                payload = _method_payload(item)
                if payload is not None:
                    deposit_method(store, research.research_id, *payload, now)
            continue
        if field in {"method_body", "body", "new_method"}:
            payload = _method_payload(value)
            if payload is not None:
                deposit_method(store, research.research_id, *payload, now)
