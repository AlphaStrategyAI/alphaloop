from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.metrics import SimulationReport
    from engine.strategy import StrategySpec
    from engine.verifiers import VerificationReport


class ResearchStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    AWAITING_CONFIRM = "awaiting_confirm"
    PAUSED = "paused"
    COMPLETED = "completed"
    ENDED = "ended"


class ResearchEvent(StrEnum):
    EDIT_DRAFT = "edit_draft"
    CONFIRM_RUN = "confirm_run"
    AUTO_CONTINUE = "auto_continue"
    REQUEST_CONFIRM = "request_confirm"
    PAUSE = "pause"
    CONFIRM_APPROVE = "confirm_approve"
    CONFIRM_REJECT = "confirm_reject"
    CONFIRM_PAUSE = "confirm_pause"
    RESUME = "resume"
    COMPLETE = "complete"
    BUDGET_EXHAUSTED = "budget_exhausted"
    REVERIFY_PASS = "reverify_pass"
    REVERIFY_FAIL = "reverify_fail"
    MODIFY_CONFIRM = "modify_confirm"
    EXTEND_CONFIRM = "extend_confirm"
    WAIT = "wait"


class Market(StrEnum):
    US = "US"
    CN = "CN"


class AssetClass(StrEnum):
    EQUITY = "equity"
    BOND = "bond"
    FUND = "fund"


class ChangeClass(StrEnum):
    PARAM = "param"
    MODEL = "model"
    ECONOMIC = "economic"
    COVERAGE = "coverage"


class ConfirmKind(StrEnum):
    ECONOMIC = "economic"
    COVERAGE = "coverage"
    REVIEW_BLOCKED = "review_blocked"


@dataclass(frozen=True, slots=True)
class Slot[T]:
    value: T | None = None
    locked: bool = False


@dataclass(frozen=True, slots=True)
class Universe:
    market: Market
    asset_class: AssetClass
    underlying_asset_class: AssetClass
    symbols: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.asset_class is not AssetClass.FUND and self.underlying_asset_class is not self.asset_class:
            raise ValueError("non-fund underlying asset class must match asset class")
        if self.underlying_asset_class is AssetClass.FUND:
            raise ValueError("fund underlying asset class must be equity or bond")


@dataclass(frozen=True, slots=True)
class CoverageFloor:
    min_assets: int
    min_years: int
    max_missing_pct: float


@dataclass(frozen=True, slots=True)
class MethodRef:
    method_id: str
    revision_hash: str


@dataclass(frozen=True, slots=True)
class ResearchBrief:
    thesis: Slot[str] = field(default_factory=Slot)
    universe: Slot[Universe] = field(default_factory=Slot)
    max_effective_hours: Slot[float] = field(default_factory=Slot)
    round1_methods: Slot[tuple[MethodRef, ...]] = field(default_factory=Slot)
    coverage_floor: Slot[CoverageFloor] = field(default_factory=Slot)


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ReviewReport:
    passed: bool
    findings: tuple[ReviewFinding, ...]
    required_changes: str | None = None


@dataclass(frozen=True, slots=True)
class Attempt:
    attempt_id: str
    number: int
    change_class: ChangeClass
    spec: StrategySpec
    simulation: SimulationReport
    verification: VerificationReport
    review: ReviewReport
    data_snapshot_path: Path | None = None
    evidence_paths: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class RoundDraft:
    version_number: int
    round_number: int
    attempt: Attempt


@dataclass(frozen=True, slots=True)
class Round:
    round_id: str
    number: int
    accepted_attempt: Attempt
    completed_at: datetime

    def __post_init__(self) -> None:
        if not self.accepted_attempt.review.passed:
            raise ValueError("a successful Round requires a passed review")


@dataclass(frozen=True, slots=True)
class Version:
    version_id: str
    number: int
    brief_snapshot: ResearchBrief
    rounds: tuple[Round, ...]
    opened_at: datetime
    opened_by: str
    confirmed_changes: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class ConfirmRequest:
    request_id: str
    kind: ConfirmKind
    proposed_change: str
    reason: str
    effect: str
    change_class: ChangeClass = ChangeClass.ECONOMIC
    patch: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class Reverification:
    round_id: str
    method_id: str
    report: VerificationReport
    passed: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Research:
    research_id: str
    status: ResearchStatus
    brief: ResearchBrief
    versions: tuple[Version, ...]
    current_version_number: int | None
    pending_confirm: ConfirmRequest | None
    consecutive_review_failures: int
    effective_seconds: float
    export_eligible: bool
    created_at: datetime
    updated_at: datetime
    reverifications: tuple[Reverification, ...] = ()


def new_research(research_id: str, now: datetime) -> Research:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return Research(
        research_id=research_id,
        status=ResearchStatus.DRAFT,
        brief=ResearchBrief(),
        versions=(),
        current_version_number=None,
        pending_confirm=None,
        consecutive_review_failures=0,
        effective_seconds=0.0,
        export_eligible=False,
        created_at=now,
        updated_at=now,
        reverifications=(),
    )
