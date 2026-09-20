from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from engine.research.models import (
    MethodDefinition,
    MethodRef,
    MethodSource,
    MethodUsage,
    Research,
)
from engine.verifiers import VERIFIER_REVISIONS


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

PRESET_NAMES = {
    "scorecard.market": "市场计分卡",
    "overfit.walk": "走样检验",
    "stability.oos": "样本外稳定",
    "crowding.load": "拥挤度",
    "cost.turnover": "换手成本",
}


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


def seed_preset_methods(store: SQLiteStore, now: datetime | None = None) -> None:
    if store.list_method_definitions():
        return
    created_at = now or datetime(2026, 1, 1, tzinfo=UTC)
    for method_id, meta in VERIFIER_REVISIONS.items():
        body = json.dumps(dict(meta), sort_keys=True)
        store.insert_method_definition(
            MethodDefinition(
                method_id=method_id,
                revision_hash=str(meta["revision"]),
                name=PRESET_NAMES[method_id],
                description=body,
                body=body,
                source=MethodSource.PRESET,
                deposited_from_research_id=None,
                created_at=created_at,
                supersedes=None,
            )
        )


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
