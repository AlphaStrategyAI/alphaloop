"""Closed proposal records. No research imports, so the store can structure them."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FieldChange:
    """One typed brief change. ``source`` is never an implied agreement."""

    field: str
    value_kind: str
    source: str
    quote_ref: str = ""
    text: str = ""
    market: str = ""
    asset: str = ""
    symbols: tuple[str, ...] = ()
    hours: float | None = None
    method_ids: tuple[str, ...] = ()
    min_assets: int | None = None
    min_years: int | None = None
    max_missing_pct: float | None = None


@dataclass(frozen=True, slots=True)
class QuoteRef:
    ref: str
    text: str


@dataclass(frozen=True, slots=True)
class OpenQuestion:
    field: str
    question: str
    changes_meaning: bool = False


@dataclass(frozen=True, slots=True)
class CapabilityMatch:
    constraint: str
    capability: str
    supported: bool = False
    note: str = ""


@dataclass(frozen=True, slots=True)
class MaterialQuery:
    """Public literature query. Terms come from an allowlist, never the raw thesis."""

    public_terms: tuple[str, ...] = ()
    provider_id: str = ""
    purpose: str = ""
    policy_revision: str = ""


@dataclass(frozen=True, slots=True)
class Proposal:
    """A schema-limited reading of one draft turn. It does not authorize a run."""

    proposal_id: str
    base_revision: int
    kind: str = "interpret_brief"
    intent: str = "provide"
    quote_refs: tuple[QuoteRef, ...] = ()
    changes: tuple[FieldChange, ...] = ()
    open_questions: tuple[OpenQuestion, ...] = ()
    capability_match: tuple[CapabilityMatch, ...] = ()
    material_query: MaterialQuery | None = None
    executable_rule: str = ""
    executable_rule_source: str = ""
    original_thesis: str = ""
    meaning_note: str = ""
    brief_fingerprint: str = ""
    named_source: str = ""
    requires_quotes: bool = False
    block_code: str = ""
    next_step: str = ""
    llm_calls: int = 0
    constraints_waived: bool = False
    primary_question: str = ""
    llm_note: str = ""
