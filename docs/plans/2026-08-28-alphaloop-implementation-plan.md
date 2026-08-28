# alphaloop Alpha Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first alpha research engine and Night desktop that turns a five-slot strategy brief into a benchmarked, independently runnable strategy pack without placing orders.
**Architecture:** A Python 3.12 engine owns the canonical research state machine, strategy simulation, verification, mandatory reviewer gate, persistence, and export contracts. A Tauri 2 process owns the engine sidecar for native sessions while React renders the seven Night views; the two-command CLI can own the same engine for headless sessions under a single pid/lock contract. SQLite stores transactional state and heartbeats, files store frozen materials and exported packs, and JSON Schema defines process boundaries.
**Tech Stack:** Python 3.12, pandas, NumPy, httpx, yfinance-style and AKShare adapters, SQLite, JSON Schema, pytest, Tauri 2, Rust, React, TypeScript, Vite, Vitest, Testing Library, PyInstaller
## Global Constraints
**Source of truth:** This implementation plan is the source of truth for coding and supersedes `docs/plans/2026-08-28-alphaloop-tech-design.md`.
**Order execution:** alphaloop does NOT place orders in v1.
**Strategy handoff:** Strategy pack must be independently backtest-runnable.
**Reserved live-trading port:** `ExecutionPort` / `Broker` is a typed interface with a `NotImplemented` stub that is never called by the desktop.
**Trading UI:** No 下单 UI.
**US equity benchmark:** S&P 500 (`SPX`).
**CN equity benchmark:** CSI 300 (`000300.SH`).
**US bond benchmark:** Bloomberg US Agg proxy (`AGG`).
**CN bond benchmark:** ChinaBond New Composite Wealth Index / 中债-新综合财富（总值）指数 (`CBA00101.CS`, fetched with AKShare `bond_new_composite_index_cbond(indicator="财富", period="总值")`).
**Fund benchmark:** Funds follow their declared underlying asset class.
**Required round metrics:** total/annualized return, excess vs benchmark, Sharpe, volatility, max drawdown.
**Primary pass rules:** `sharpe_oos > 0`, `excess_ann > 0`, and `max_drawdown >= max_drawdown_floor` where the default floor is `-0.25`.
**Additional verifier gates:** walk-forward, OOS stability, crowding, and transaction cost.
**Threshold change:** Changing any validation threshold is a new method revision and an economic confirmation.
**Reviewer:** Every automatic research round runs a subagent review.
**Reviewer result:** `{passed: bool, findings: [...], required_changes?: ...}`.
**Reviewer failure:** A failed review cannot append a successful `Round` and cannot advance `Version`.
**Reviewer retry cap:** `3` consecutive review failures under the same version.
**Reviewer timeout:** Never timeout-auto-approve the reviewer.
**Native lifecycle:** Native Tauri app Quit / last window closed on Mac/Win/Linux ⇒ stop the engine sidecar; one process tree; no orphan daemon after app exit.
**Web lifecycle:** Web UI tab close ⇒ engine keeps running; the desktop app is a process owner and a browser is not.
**Headless lifecycle:** CLI `start` owns the engine for research without the GUI.
**Single owner:** Desktop and CLI owners use one pid/lock file and must not double-start.
**Dialogue scope:** Dialogue is not a general chatbot; it only elicits `thesis`, `universe`, `max_effective_hours`, `round1_methods`, and `coverage_floor`, enriches them with public materials, locks them, shows confirm-run, and then starts research.
**Frequency:** v1 bar = daily (`1d`).
**Strategy side:** `long_only` or `long_short`; default `long_only`.
**Desktop frame:** `1440×900`.
**Rail:** `148px`.
**Logo:** `148×148`, with Logo + nav vertically centered.
**Theme:** Night / Dark only.
**Night colors:** `void #07090C`, `glass #12161C`, `ink #E8EEF5`, `mute #8B97A8`, `line #1E2530`, `cyan #5EEAD4`, `run #60A5FA`, `ok #34D399`, `stop #F87171`, `hold #FBBF24`.
**Cyan:** Only confirm-run and awaiting-confirm use cyan/glow.
**Research list:** awaiting-confirm is a primary card, not an ordinary row.
**Confirmation UI:** confirm-run and awaiting-confirm are two cards, never one modal.
**CLI surface:** only `start` and `status`.
**Desktop stack:** Tauri 2 + React + TypeScript.
**Engine stack:** Python 3.12.
**Persistence:** SQLite + files.
**Contracts:** JSON Schema.
**Tests:** pytest for engine and Vitest for UI.
---

**References:** [product positioning](../requirements/product-positioning.md), [product design v0.0.1](../requirements/product-design-v0_0_1.md), [UI design v0.0.1](../requirements/ui-design-v0_0_1.md), and [Issue #111](https://github.com/AlphaStrategyAI/alphaloop/issues/111).

## File-Structure Map

```text
.
├── pyproject.toml                              # Python 3.12 package, dependencies, CLI/engine entry points, pytest config
├── contracts/
│   ├── research.schema.json                    # persisted and IPC-safe research envelope
│   ├── desktop-api.schema.json                 # desktop request/response contract
│   └── strategy-pack.schema.json               # exported manifest contract
├── engine/
│   ├── __init__.py
│   ├── strategy.py                             # AlphaStrategy, MarketPanel, StrategySpec, reference mean reversion, backtest
│   ├── execution.py                            # reserved ExecutionPort/Broker and disabled stub only
│   ├── metrics.py                              # daily benchmark map and SimulationReport calculations
│   ├── verifiers.py                            # primary scorecard and four additional frozen gates
│   ├── export.py                               # self-contained pack writer and eligibility
│   ├── main.py                                 # owned engine process entry point and signal/EOF shutdown
│   ├── dialogue/
│   │   ├── __init__.py
│   │   ├── intent.py                           # Intent enum, interpret(message, research), off-topic rejection
│   │   └── slots.py                            # five-slot reducer, question policy, lock/confirm-run readiness
│   ├── research/
│   │   ├── __init__.py
│   │   ├── models.py                           # Research, Version, Round, Attempt, ReviewReport and six statuses
│   │   ├── state_machine.py                    # product 4.8 transitions and ConfirmRequest handling
│   │   ├── gather.py                           # SEC/papers/local material and Yahoo/AKShare-style data ports
│   │   ├── specify.py                          # StrategySpec construction and param/model/economic/coverage classifier
│   │   ├── simulate.py                         # one-day simulation orchestration
│   │   ├── loop.py                             # gather→specify→simulate→verify→review→decide loop
│   │   ├── clock.py                            # running-only TimeBudget
│   │   ├── store.py                            # SQLite transactions, completed-round resume, heartbeat
│   │   └── runtime.py                          # cross-platform lifetime pid/lock and owner record
│   └── review/
│       ├── __init__.py
│       └── subagent.py                         # frozen rubric, second-LLM ReviewerPort, strict JSON result
├── materials/                                  # user-local and gathered source snapshots; ignored except README
│   └── README.md
├── apps/
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py                             # public start/status parser and detached CLI ownership
│   └── desktop/
│       ├── package.json
│       ├── package-lock.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       ├── index.html
│       ├── src/
│       │   ├── main.tsx
│       │   ├── App.tsx                         # seven view components and route/state selection
│       │   ├── contracts.ts                    # generated/narrowed desktop types
│       │   ├── night.css                       # locked Night tokens, shell, cards, transitions
│       │   └── App.test.tsx
│       └── src-tauri/
│           ├── Cargo.toml
│           ├── build.rs
│           ├── tauri.conf.json
│           ├── capabilities/default.json
│           ├── src/lib.rs                      # Tauri events and sidecar setup
│           ├── src/main.rs
│           ├── src/commands.rs                  # authenticated loopback desktop commands
│           ├── src/sidecar.rs                  # owned/attached process supervisor
│           └── tests/sidecar_lifecycle.rs
├── packaging/
│   └── alphaloop-engine.spec                   # native PyInstaller sidecar
├── scripts/
│   └── stage_sidecar.py                        # target-triple binary staging
└── tests/
    ├── test_state_machine.py
    ├── test_strategy.py
    ├── test_dialogue.py
    ├── test_gather_specify.py
    ├── test_metrics.py
    ├── test_verifiers.py
    ├── test_reviewer.py
    ├── test_loop_runtime.py
    ├── test_export_pack.py
    └── test_cli.py
```

Task order is intentionally coupled: each task consumes only interfaces already produced, and each commit leaves a testable vertical increment. Keep code DRY, apply YAGNI to every new abstraction, write each failing test before production code, and do not combine task commits.

### Task 1: Canonical Research Types and State Machine

**Files:**
- Create: `pyproject.toml`
- Create: `engine/__init__.py`
- Create: `engine/research/__init__.py`
- Create: `engine/research/models.py`
- Create: `engine/research/state_machine.py`
- Create: `contracts/research.schema.json`
- Test: `tests/test_state_machine.py`

**Interfaces:**
- Consumes: no application interfaces; Python 3.12 standard library only
- Produces: `new_research(research_id: str, now: datetime) -> Research`; `all_slots_locked(brief: ResearchBrief) -> bool`; `transition(research: Research, event: ResearchEvent, now: datetime, request: ConfirmRequest | None = None) -> Research`; `Research`, `Version`, `Round`, `Attempt`, `RoundDraft`, `ReviewReport`, `Reverification`, `ResearchStatus`, `ResearchEvent`, `ChangeClass`, `ConfirmRequest`, `ResearchBrief`, `Universe`, `CoverageFloor`, `MethodRef`

- [ ] **Step 1: Write the failing state-table test**

Create `tests/test_state_machine.py` with the complete product 4.8 table, confirm-run-as-view rule, immutable version boundary, and invalid-transition check:

```python
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from engine.research.models import (
    AssetClass,
    ConfirmKind,
    ConfirmRequest,
    CoverageFloor,
    Market,
    MethodRef,
    ResearchBrief,
    ResearchEvent,
    ResearchStatus,
    Slot,
    Universe,
    new_research,
)
from engine.research.state_machine import InvalidTransition, all_slots_locked, transition

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def locked_brief() -> ResearchBrief:
    return ResearchBrief(
        thesis=Slot("低波动量价回归", True),
        universe=Slot(
            Universe(
                market=Market.US,
                asset_class=AssetClass.EQUITY,
                underlying_asset_class=AssetClass.EQUITY,
                symbols=("AAPL", "MSFT"),
            ),
            True,
        ),
        max_effective_hours=Slot(12.0, True),
        round1_methods=Slot(
            (
                MethodRef("overfit.walk", "walk-v1"),
                MethodRef("stability.oos", "stability-v1"),
                MethodRef("crowding.load", "crowding-v1"),
                MethodRef("cost.turnover", "cost-v1"),
            ),
            True,
        ),
        coverage_floor=Slot(
            CoverageFloor(min_assets=2, min_years=10, max_missing_pct=5.0),
            True,
        ),
    )


def with_status(status: ResearchStatus):
    research = new_research("r-1", NOW)
    return replace(research, status=status, brief=locked_brief())


def test_confirm_run_is_a_draft_view_and_opens_version_one() -> None:
    research = replace(new_research("r-1", NOW), brief=locked_brief())
    assert research.status is ResearchStatus.DRAFT
    assert all_slots_locked(research.brief)

    running = transition(research, ResearchEvent.CONFIRM_RUN, NOW)

    assert running.status is ResearchStatus.RUNNING
    assert len(running.versions) == 1
    assert running.versions[0].number == 1
    assert running.versions[0].brief_snapshot == locked_brief()


@pytest.mark.parametrize(
    ("start", "event", "expected"),
    (
        (ResearchStatus.RUNNING, ResearchEvent.AUTO_CONTINUE, ResearchStatus.RUNNING),
        (ResearchStatus.RUNNING, ResearchEvent.PAUSE, ResearchStatus.PAUSED),
        (ResearchStatus.RUNNING, ResearchEvent.COMPLETE, ResearchStatus.COMPLETED),
        (ResearchStatus.RUNNING, ResearchEvent.BUDGET_EXHAUSTED, ResearchStatus.ENDED),
        (ResearchStatus.AWAITING_CONFIRM, ResearchEvent.CONFIRM_REJECT, ResearchStatus.RUNNING),
        (ResearchStatus.AWAITING_CONFIRM, ResearchEvent.CONFIRM_PAUSE, ResearchStatus.PAUSED),
        (ResearchStatus.PAUSED, ResearchEvent.RESUME, ResearchStatus.RUNNING),
        (ResearchStatus.COMPLETED, ResearchEvent.REVERIFY_PASS, ResearchStatus.COMPLETED),
        (ResearchStatus.COMPLETED, ResearchEvent.REVERIFY_FAIL, ResearchStatus.COMPLETED),
        (ResearchStatus.PAUSED, ResearchEvent.MODIFY_CONFIRM, ResearchStatus.RUNNING),
        (ResearchStatus.COMPLETED, ResearchEvent.MODIFY_CONFIRM, ResearchStatus.RUNNING),
        (ResearchStatus.ENDED, ResearchEvent.MODIFY_CONFIRM, ResearchStatus.RUNNING),
        (ResearchStatus.ENDED, ResearchEvent.EXTEND_CONFIRM, ResearchStatus.RUNNING),
    ),
)
def test_product_state_table(
    start: ResearchStatus,
    event: ResearchEvent,
    expected: ResearchStatus,
) -> None:
    research = with_status(start)
    assert transition(research, event, NOW).status is expected


@pytest.mark.parametrize("kind", (ConfirmKind.ECONOMIC, ConfirmKind.COVERAGE, ConfirmKind.REVIEW_BLOCKED))
def test_running_can_wait_without_opening_a_version(kind: ConfirmKind) -> None:
    research = with_status(ResearchStatus.RUNNING)
    request = ConfirmRequest(
        request_id=f"c-{kind.value}",
        kind=kind,
        proposed_change="保持同一版本等待人工判断",
        reason="自动研究不能安全继续",
        effect="确认后才会创建新版本",
    )

    waiting = transition(research, ResearchEvent.REQUEST_CONFIRM, NOW, request)

    assert waiting.status is ResearchStatus.AWAITING_CONFIRM
    assert waiting.pending_confirm == request
    assert waiting.versions == research.versions


def test_approval_applies_patch_and_opens_version_but_rejection_does_not() -> None:
    request = ConfirmRequest(
        "c-1",
        ConfirmKind.ECONOMIC,
        "改信号",
        "验证失败",
        "新版本",
        patch=(("thesis", "带拥挤过滤的低波动回归"),),
    )
    waiting = replace(
        with_status(ResearchStatus.AWAITING_CONFIRM),
        pending_confirm=request,
    )

    approved = transition(waiting, ResearchEvent.CONFIRM_APPROVE, NOW)
    rejected = transition(waiting, ResearchEvent.CONFIRM_REJECT, NOW)

    assert approved.status is ResearchStatus.RUNNING
    assert len(approved.versions) == 1
    assert approved.versions[0].number == 1
    assert approved.brief.thesis.value == "带拥挤过滤的低波动回归"
    assert approved.versions[0].confirmed_changes == request.patch
    assert rejected.status is ResearchStatus.RUNNING
    assert rejected.versions == waiting.versions


def test_wait_pause_complete_and_end_never_consume_time() -> None:
    for status in (
        ResearchStatus.DRAFT,
        ResearchStatus.AWAITING_CONFIRM,
        ResearchStatus.PAUSED,
        ResearchStatus.COMPLETED,
        ResearchStatus.ENDED,
    ):
        research = replace(with_status(status), effective_seconds=91.0)
        event = {
            ResearchStatus.DRAFT: ResearchEvent.EDIT_DRAFT,
            ResearchStatus.AWAITING_CONFIRM: ResearchEvent.WAIT,
            ResearchStatus.PAUSED: ResearchEvent.WAIT,
            ResearchStatus.COMPLETED: ResearchEvent.REVERIFY_PASS,
            ResearchStatus.ENDED: ResearchEvent.WAIT,
        }[status]
        assert transition(research, event, NOW).effective_seconds == 91.0


def test_invalid_transition_is_rejected() -> None:
    with pytest.raises(InvalidTransition, match="draft.*complete"):
        transition(with_status(ResearchStatus.DRAFT), ResearchEvent.COMPLETE, NOW)
```

- [ ] **Step 2: Run the state-table test and verify RED**

Run: `python -m pytest tests/test_state_machine.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'engine'`.

- [ ] **Step 3: Add the minimal canonical models, transition reducer, package config, and JSON contract**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=75", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "alphaloop"
version = "0.2.0"
requires-python = ">=3.12"
dependencies = [
  "akshare",
  "httpx",
  "jsonschema",
  "numpy",
  "pandas",
  "platformdirs",
  "portalocker",
  "yfinance",
]

[project.optional-dependencies]
dev = ["build", "mypy", "pandas-stubs", "pyinstaller", "pytest", "ruff"]

[project.scripts]
alphaloop = "apps.cli.main:main"
alphaloop-engine = "engine.main:main"

[tool.setuptools.packages.find]
include = ["engine*", "apps*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
```

Create `engine/__init__.py`:

```python
"""alphaloop engine."""
```

Create `engine/research/__init__.py`:

```python
"""Research domain and orchestration."""
```

Create `engine/research/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from engine.metrics import SimulationReport
    from engine.strategy import StrategySpec
    from engine.verifiers import VerificationReport

T = TypeVar("T")


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
class Slot(Generic[T]):
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
```

Create `engine/research/state_machine.py`:

```python
from dataclasses import replace
from datetime import datetime

from engine.research.models import (
    ConfirmRequest,
    Research,
    ResearchBrief,
    ResearchEvent,
    ResearchStatus,
    Slot,
    Version,
)


class InvalidTransition(ValueError):
    """Raised when an event is not valid for the current research status."""


def all_slots_locked(brief: ResearchBrief) -> bool:
    slots = (
        brief.thesis,
        brief.universe,
        brief.max_effective_hours,
        brief.round1_methods,
        brief.coverage_floor,
    )
    return all(slot.locked and slot.value is not None for slot in slots)


def _open_version(research: Research, now: datetime, opened_by: str) -> Research:
    brief = research.brief
    changes = research.pending_confirm.patch if research.pending_confirm else ()
    for field_name, value in changes:
        if hasattr(brief, field_name):
            brief = replace(brief, **{field_name: Slot(value, True)})
    number = len(research.versions) + 1
    version = Version(
        version_id=f"{research.research_id}-v{number}",
        number=number,
        brief_snapshot=brief,
        rounds=(),
        opened_at=now,
        opened_by=opened_by,
        confirmed_changes=changes,
    )
    return replace(
        research,
        status=ResearchStatus.RUNNING,
        brief=brief,
        versions=research.versions + (version,),
        current_version_number=number,
        pending_confirm=None,
        export_eligible=False,
        updated_at=now,
    )


def transition(
    research: Research,
    event: ResearchEvent,
    now: datetime,
    request: ConfirmRequest | None = None,
) -> Research:
    status = research.status
    if status is ResearchStatus.DRAFT and event is ResearchEvent.EDIT_DRAFT:
        return replace(research, updated_at=now)
    if status is ResearchStatus.DRAFT and event is ResearchEvent.CONFIRM_RUN:
        if not all_slots_locked(research.brief):
            raise InvalidTransition("draft cannot confirm_run until all five slots are locked")
        return _open_version(research, now, "confirm_run")
    if status is ResearchStatus.RUNNING and event is ResearchEvent.AUTO_CONTINUE:
        return replace(research, updated_at=now)
    if status is ResearchStatus.RUNNING and event is ResearchEvent.REQUEST_CONFIRM:
        if request is None:
            raise InvalidTransition("request_confirm requires ConfirmRequest")
        return replace(
            research,
            status=ResearchStatus.AWAITING_CONFIRM,
            pending_confirm=request,
            updated_at=now,
        )
    if status is ResearchStatus.RUNNING and event is ResearchEvent.PAUSE:
        return replace(research, status=ResearchStatus.PAUSED, updated_at=now)
    if status is ResearchStatus.RUNNING and event is ResearchEvent.COMPLETE:
        return replace(
            research,
            status=ResearchStatus.COMPLETED,
            export_eligible=True,
            updated_at=now,
        )
    if status is ResearchStatus.RUNNING and event is ResearchEvent.BUDGET_EXHAUSTED:
        return replace(research, status=ResearchStatus.ENDED, updated_at=now)
    if status is ResearchStatus.AWAITING_CONFIRM and event is ResearchEvent.CONFIRM_APPROVE:
        return _open_version(research, now, "economic_confirm")
    if status is ResearchStatus.AWAITING_CONFIRM and event is ResearchEvent.CONFIRM_REJECT:
        return replace(
            research,
            status=ResearchStatus.RUNNING,
            pending_confirm=None,
            consecutive_review_failures=0,
            updated_at=now,
        )
    if status is ResearchStatus.AWAITING_CONFIRM and event is ResearchEvent.CONFIRM_PAUSE:
        return replace(
            research,
            status=ResearchStatus.PAUSED,
            pending_confirm=None,
            updated_at=now,
        )
    if status is ResearchStatus.PAUSED and event is ResearchEvent.RESUME:
        return replace(research, status=ResearchStatus.RUNNING, updated_at=now)
    if status is ResearchStatus.COMPLETED and event is ResearchEvent.REVERIFY_PASS:
        return replace(research, updated_at=now)
    if status is ResearchStatus.COMPLETED and event is ResearchEvent.REVERIFY_FAIL:
        return replace(research, export_eligible=False, updated_at=now)
    if (
        status in {ResearchStatus.PAUSED, ResearchStatus.COMPLETED, ResearchStatus.ENDED}
        and event is ResearchEvent.MODIFY_CONFIRM
    ):
        return _open_version(research, now, "modified_settings_confirm")
    if status is ResearchStatus.ENDED and event is ResearchEvent.EXTEND_CONFIRM:
        return _open_version(research, now, "extended_budget_confirm")
    if event is ResearchEvent.WAIT and status in {
        ResearchStatus.AWAITING_CONFIRM,
        ResearchStatus.PAUSED,
        ResearchStatus.ENDED,
    }:
        return research
    raise InvalidTransition(f"{status.value} cannot handle {event.value}")
```

Create `contracts/research.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://alphaloop.local/contracts/research.schema.json",
  "title": "ResearchEnvelope",
  "type": "object",
  "additionalProperties": false,
  "required": ["research_id", "status", "current_version_number", "effective_seconds"],
  "properties": {
    "research_id": {"type": "string", "minLength": 1},
    "status": {
      "enum": ["draft", "running", "awaiting_confirm", "paused", "completed", "ended"]
    },
    "current_version_number": {"type": ["integer", "null"], "minimum": 1},
    "effective_seconds": {"type": "number", "minimum": 0}
  }
}
```

- [ ] **Step 4: Run the state-table test and static checks**

Run: `python -m pytest tests/test_state_machine.py -q && python -m mypy engine/research`

Expected: PASS with `20 passed`; mypy exits `0`.

- [ ] **Step 5: Commit the canonical domain**

```bash
git add pyproject.toml engine/__init__.py engine/research contracts/research.schema.json tests/test_state_machine.py
git commit -m "feat(engine): define research state machine"
```

### Task 2: Alpha Strategy Contract and Daily Reference Backtest

**Files:**
- Create: `engine/strategy.py`
- Test: `tests/test_strategy.py`

**Interfaces:**
- Consumes: `Universe`, `AssetClass` from `engine.research.models`
- Produces: `AlphaStrategy.generate_signals(self, data: MarketPanel) -> pd.DataFrame`; `AlphaStrategy.to_executable(self) -> Path`; `StrategySpec`; `MarketPanel`; `MeanReversionStrategy`; `run_daily_backtest(strategy: AlphaStrategy, data: MarketPanel) -> pd.Series`

- [ ] **Step 1: Write the failing strategy protocol and reference-backtest test**

Create `tests/test_strategy.py`:

```python
from datetime import UTC, datetime

import pandas as pd

from engine.research.models import AssetClass, Market, Universe
from engine.strategy import (
    AlphaStrategy,
    MarketPanel,
    MeanReversionStrategy,
    StrategySpec,
    run_daily_backtest,
)


def panel() -> MarketPanel:
    index = pd.date_range("2026-01-01", periods=5, tz=UTC)
    prices = pd.DataFrame(
        {"AAA": [10.0, 8.0, 9.0, 10.0, 11.0], "BBB": [10.0, 12.0, 11.0, 10.0, 9.0]},
        index=index,
    )
    return MarketPanel(prices=prices, observed_at=datetime(2026, 1, 6, tzinfo=UTC))


def strategy(side: str = "long_only") -> MeanReversionStrategy:
    universe = Universe(
        market=Market.US,
        asset_class=AssetClass.EQUITY,
        underlying_asset_class=AssetClass.EQUITY,
        symbols=("AAA", "BBB"),
    )
    spec = StrategySpec(
        id="mean-reversion-test",
        thesis_locked="one-day cross-sectional reversal",
        universe=universe,
        frequency="1d",
        side=side,
        method_set=(),
        model_family="mean_reversion",
        lookback_days=2,
        entry_z=0.5,
        max_drawdown_floor=-0.25,
    )
    return MeanReversionStrategy(spec=spec)


def test_reference_strategy_satisfies_protocol_and_signal_domain() -> None:
    instance = strategy()
    assert isinstance(instance, AlphaStrategy)

    signals = instance.generate_signals(panel())

    assert list(signals.columns) == ["AAA", "BBB"]
    assert set(signals.stack().unique()) <= {-1.0, 0.0, 1.0}
    assert (signals >= 0).all().all()


def test_long_short_reference_strategy_can_short() -> None:
    signals = strategy("long_short").generate_signals(panel())
    assert -1.0 in set(signals.stack().unique())


def test_backtest_uses_previous_day_signal_without_lookahead() -> None:
    result = run_daily_backtest(strategy(), panel())
    assert result.index.equals(panel().prices.index)
    assert result.iloc[0] == 0.0
    assert result.iloc[1] == 0.0
    assert result.notna().all()


def test_to_executable_is_part_of_the_strategy_contract() -> None:
    assert callable(strategy().to_executable)
```

- [ ] **Step 2: Run the reference strategy test and verify RED**

Run: `python -m pytest tests/test_strategy.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'engine.strategy'`.

- [ ] **Step 3: Implement the canonical strategy types and no-lookahead backtest**

Create `engine/strategy.py`:

```python
from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from engine.research.models import MethodRef, Universe

Frequency = Literal["1d"]
Side = Literal["long_only", "long_short"]


@dataclass(frozen=True, slots=True)
class MarketPanel:
    prices: pd.DataFrame
    observed_at: datetime
    benchmark_prices: pd.Series | None = None

    def __post_init__(self) -> None:
        if self.prices.empty or not self.prices.index.is_monotonic_increasing:
            raise ValueError("prices must be non-empty and sorted by date")
        if self.prices.isna().all(axis=None):
            raise ValueError("prices cannot be entirely missing")


@dataclass(frozen=True, slots=True)
class StrategySpec:
    id: str
    thesis_locked: str
    universe: Universe
    frequency: Frequency
    method_set: tuple[MethodRef, ...]
    model_family: str
    lookback_days: int
    entry_z: float
    side: Side = "long_only"
    max_drawdown_floor: float = -0.25

    def __post_init__(self) -> None:
        if self.frequency != "1d":
            raise ValueError("v1 supports daily bars only")
        if not -1.0 < self.max_drawdown_floor < 0.0:
            raise ValueError("max_drawdown_floor must be between -1 and 0")


@runtime_checkable
class AlphaStrategy(Protocol):
    id: str
    thesis: str
    universe: Universe
    frequency: Frequency
    side: Side

    def generate_signals(self, data: MarketPanel) -> pd.DataFrame:
        raise NotImplementedError

    def to_executable(self) -> Path:
        raise NotImplementedError


@dataclass(slots=True)
class MeanReversionStrategy:
    spec: StrategySpec

    @property
    def id(self) -> str:
        return self.spec.id

    @property
    def thesis(self) -> str:
        return self.spec.thesis_locked

    @property
    def universe(self) -> Universe:
        return self.spec.universe

    @property
    def frequency(self) -> Frequency:
        return self.spec.frequency

    @property
    def side(self) -> Side:
        return self.spec.side

    def generate_signals(self, data: MarketPanel) -> pd.DataFrame:
        returns = data.prices.pct_change(fill_method=None)
        score = -returns.rolling(self.spec.lookback_days).mean()
        dispersion = score.std(axis=1).replace(0.0, np.nan)
        zscore = score.sub(score.mean(axis=1), axis=0).div(dispersion, axis=0)
        signals = pd.DataFrame(0.0, index=data.prices.index, columns=data.prices.columns)
        signals[zscore >= self.spec.entry_z] = 1.0
        if self.spec.side == "long_short":
            signals[zscore <= -self.spec.entry_z] = -1.0
        return signals

    def to_executable(self) -> Path:
        target = Path(tempfile.mkdtemp(prefix="alphaloop-strategy-"))
        spec = asdict(self.spec)
        spec["universe"]["market"] = self.spec.universe.market.value
        spec["universe"]["asset_class"] = self.spec.universe.asset_class.value
        spec["universe"]["underlying_asset_class"] = (
            self.spec.universe.underlying_asset_class.value
        )
        spec["method_set"] = [asdict(item) for item in self.spec.method_set]
        (target / "spec.json").write_text(
            json.dumps(spec, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        runner = target / "run_backtest.py"
        runner.write_text(
            "from pathlib import Path\n"
            "import json\n"
            "print(json.loads(Path('spec.json').read_text(encoding='utf-8'))['id'])\n",
            encoding="utf-8",
        )
        return runner


def run_daily_backtest(strategy: AlphaStrategy, data: MarketPanel) -> pd.Series:
    signals = strategy.generate_signals(data).shift(1).fillna(0.0)
    gross = signals.abs().sum(axis=1).replace(0.0, 1.0)
    weights = signals.div(gross, axis=0)
    asset_returns = data.prices.pct_change(fill_method=None).fillna(0.0)
    return (weights * asset_returns).sum(axis=1).rename("strategy_return")
```

- [ ] **Step 4: Run the strategy test and verify GREEN**

Run: `python -m pytest tests/test_strategy.py -q && python -m mypy engine/strategy.py`

Expected: PASS with `4 passed`; mypy exits `0`.

- [ ] **Step 5: Commit the strategy contract**

```bash
git add engine/strategy.py tests/test_strategy.py
git commit -m "feat(engine): add alpha strategy contract"
```

### Task 3: Purposeful Five-Slot Dialogue

**Files:**
- Create: `engine/dialogue/__init__.py`
- Create: `engine/dialogue/intent.py`
- Create: `engine/dialogue/slots.py`
- Test: `tests/test_dialogue.py`

**Interfaces:**
- Consumes: `Research`, `ResearchBrief`, `Slot`, `Universe`, `CoverageFloor`, `MethodRef`
- Produces: `interpret(message: str, research: Research) -> Intent`; `apply_intent(research: Research, intent: Intent, now: datetime) -> Research`; `next_question(research: Research) -> DialoguePrompt`; `IntentKind`; `Intent`; `SlotName`; `DialoguePrompt`

The five-slot policy is fixed and sequential when a message does not safely fill multiple slots:

| Slot | Question policy | Parser | Public-material proposal used in Task 4 |
|---|---|---|---|
| `thesis` | Ask what repeatable market behavior should earn the return and what signal represents it. | A research-direction phrase of at least four characters; reject unrelated conversation. | Search papers/EDGAR for the named factor and propose a one-sentence falsifiable mechanism. |
| `universe` | Ask market, asset class, and symbols or fund exposure. | Detect US/美股 or CN/A股/中国 and equity/bond/fund; funds must resolve `underlying_asset_class`. | Fetch benchmark history and asset availability; propose US equity for “美股低波动回归”. |
| `max_effective_hours` | Ask for running-only hours, explicitly excluding pause/wait. | Parse `N小时` where `0 < N <= 720`. | Show historical data-fetch/simulation volume, but never silently choose a value. |
| `round1_methods` | Ask which frozen verifier revisions start round 1. | Map 走样检验/样本外稳定/拥挤度/成本 to the four locked IDs. | Literature and SPX volatility evidence proposes `overfit.walk`, `stability.oos`, and `crowding.load`; `cost.turnover` is always included. |
| `coverage_floor` | Ask minimum assets, history years, and maximum missing percentage. | Parse `至少N个`, `N年`, `缺失不超过N%`. | Data adapters measure available assets/history/missingness and propose a floor no stricter than observed coverage. |

- [ ] **Step 1: Write the failing dialogue state-machine test**

Create `tests/test_dialogue.py`:

```python
from datetime import UTC, datetime

from engine.dialogue.intent import IntentKind, interpret
from engine.dialogue.slots import SlotName, apply_intent, next_question
from engine.research.models import AssetClass, Market, new_research

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def test_direction_message_fills_relevant_slots_but_does_not_start() -> None:
    research = new_research("r-dialogue", NOW)

    intent = interpret("我想研究美股低波动回归", research)
    updated = apply_intent(research, intent, NOW)

    assert intent.kind is IntentKind.PROVIDE
    assert updated.brief.thesis.value == "美股低波动回归"
    assert updated.brief.universe.value is not None
    assert updated.brief.universe.value.market is Market.US
    assert updated.brief.universe.value.asset_class is AssetClass.EQUITY
    assert not updated.brief.thesis.locked
    assert updated.status.value == "draft"
    assert next_question(updated).slot is SlotName.THESIS


def test_each_slot_requires_explicit_lock_before_confirm_run() -> None:
    research = new_research("r-lock", NOW)
    messages = (
        "研究美股低波动回归",
        "锁定大致原理",
        "锁定资产类别",
        "最长有效研究时间12小时并锁定",
        "第一轮用走样检验、样本外稳定、拥挤度、换手成本并锁定",
        "最低覆盖至少50个资产、10年、缺失不超过5%并锁定",
    )
    for message in messages:
        research = apply_intent(research, interpret(message, research), NOW)

    prompt = next_question(research)
    assert prompt.slot is None
    assert prompt.message == "五项研究设定已锁定，请检查确认开跑卡。"


def test_off_topic_is_rejected_without_mutation() -> None:
    research = new_research("r-offtopic", NOW)
    intent = interpret("给我讲个笑话", research)

    assert intent.kind is IntentKind.OFF_TOPIC
    assert apply_intent(research, intent, NOW) == research
    assert "只用于完善五项研究设定" in intent.response


def test_confirmation_cannot_be_inferred_from_casual_affirmation() -> None:
    research = new_research("r-yes", NOW)
    intent = interpret("好啊", research)
    assert intent.kind is IntentKind.OFF_TOPIC
```

- [ ] **Step 2: Run the dialogue test and verify RED**

Run: `python -m pytest tests/test_dialogue.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'engine.dialogue'`.

- [ ] **Step 3: Implement the deterministic intent parser, reducer, and question policy**

Create `engine/dialogue/__init__.py`:

```python
"""Purpose-limited research brief dialogue."""
```

Create `engine/dialogue/intent.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from engine.research.models import (
    AssetClass,
    CoverageFloor,
    Market,
    MethodRef,
    Research,
    Universe,
)


class IntentKind(StrEnum):
    PROVIDE = "provide"
    LOCK = "lock"
    UNLOCK = "unlock"
    OFF_TOPIC = "off_topic"


@dataclass(frozen=True, slots=True)
class Intent:
    kind: IntentKind
    updates: tuple[tuple[str, Any], ...] = ()
    locks: tuple[str, ...] = ()
    unlocks: tuple[str, ...] = ()
    response: str = ""


METHOD_WORDS = {
    "走样检验": MethodRef("overfit.walk", "walk-v1"),
    "样本外稳定": MethodRef("stability.oos", "stability-v1"),
    "拥挤度": MethodRef("crowding.load", "crowding-v1"),
    "换手成本": MethodRef("cost.turnover", "cost-v1"),
}
SLOT_WORDS = {
    "大致原理": "thesis",
    "资产类别": "universe",
    "最长有效研究时间": "max_effective_hours",
    "最长研究时间": "max_effective_hours",
    "第一轮": "round1_methods",
    "最低覆盖": "coverage_floor",
}


def _universe(message: str) -> Universe | None:
    market = Market.US if re.search(r"美股|美国|US", message, re.I) else None
    market = Market.CN if re.search(r"A股|中国|沪深|CN", message, re.I) else market
    asset = AssetClass.BOND if "债" in message else None
    asset = AssetClass.FUND if "基金" in message else asset
    asset = AssetClass.EQUITY if re.search(r"股|股票", message) else asset
    if market is None or asset is None:
        return None
    underlying = AssetClass.BOND if asset is AssetClass.FUND and "债" in message else asset
    if asset is AssetClass.FUND and underlying is AssetClass.FUND:
        return None
    return Universe(market, asset, underlying, ())


def interpret(message: str, research: Research) -> Intent:
    text = message.strip()
    if not text:
        return Intent(IntentKind.OFF_TOPIC, response="请输入与五项研究设定有关的信息。")
    unlocks = tuple(value for key, value in SLOT_WORDS.items() if key in text and "解锁" in text)
    if unlocks:
        return Intent(IntentKind.UNLOCK, unlocks=unlocks)
    locks = tuple(value for key, value in SLOT_WORDS.items() if key in text and "锁定" in text)
    updates: list[tuple[str, Any]] = []
    universe = _universe(text)
    if universe is not None:
        updates.append(("universe", universe))
        thesis = re.sub(r"我想|研究|锁定|并锁定", "", text).strip()
        if len(thesis) >= 4:
            updates.append(("thesis", thesis))
    hours = re.search(r"(\d+(?:\.\d+)?)\s*小时", text)
    if hours:
        value = float(hours.group(1))
        if not 0 < value <= 720:
            return Intent(IntentKind.OFF_TOPIC, response="有效研究时间必须大于0且不超过720小时。")
        updates.append(("max_effective_hours", value))
    methods = tuple(ref for word, ref in METHOD_WORDS.items() if word in text)
    if methods:
        updates.append(("round1_methods", methods))
    assets = re.search(r"至少\s*(\d+)\s*个", text)
    years = re.search(r"(\d+)\s*年", text)
    missing = re.search(r"缺失不超过\s*(\d+(?:\.\d+)?)\s*%", text)
    if assets and years and missing:
        updates.append(
            (
                "coverage_floor",
                CoverageFloor(
                    min_assets=int(assets.group(1)),
                    min_years=int(years.group(1)),
                    max_missing_pct=float(missing.group(1)),
                ),
            )
        )
    if updates or locks:
        return Intent(IntentKind.PROVIDE, tuple(updates), locks)
    return Intent(
        IntentKind.OFF_TOPIC,
        response="这条对话只用于完善五项研究设定，请回答当前研究问题。",
    )
```

Create `engine/dialogue/slots.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from engine.dialogue.intent import Intent, IntentKind
from engine.research.models import Research, ResearchBrief, Slot
from engine.research.state_machine import all_slots_locked


class SlotName(StrEnum):
    THESIS = "thesis"
    UNIVERSE = "universe"
    MAX_EFFECTIVE_HOURS = "max_effective_hours"
    ROUND1_METHODS = "round1_methods"
    COVERAGE_FLOOR = "coverage_floor"


@dataclass(frozen=True, slots=True)
class DialoguePrompt:
    slot: SlotName | None
    message: str


QUESTIONS = {
    SlotName.THESIS: "这个策略凭什么获得收益，哪个可观察信号代表这个机制？",
    SlotName.UNIVERSE: "请锁定市场、资产类别；基金还要说明底层是股票还是债券。",
    SlotName.MAX_EFFECTIVE_HOURS: "最多允许多少小时的有效研究时间？暂停和等待确认不计时。",
    SlotName.ROUND1_METHODS: "第一轮使用哪些冻结验证方法？",
    SlotName.COVERAGE_FLOOR: "最低覆盖需要多少资产、多少年历史、最多多少缺失比例？",
}


def _set_slot(brief: ResearchBrief, name: str, value: object | None, lock: bool | None) -> ResearchBrief:
    current = getattr(brief, name)
    next_slot = Slot(
        current.value if value is None else value,
        current.locked if lock is None else lock,
    )
    return replace(brief, **{name: next_slot})


def apply_intent(research: Research, intent: Intent, now: datetime) -> Research:
    if intent.kind is IntentKind.OFF_TOPIC:
        return research
    brief = research.brief
    for name, value in intent.updates:
        brief = _set_slot(brief, name, value, None)
    for name in intent.locks:
        if getattr(brief, name).value is not None:
            brief = _set_slot(brief, name, None, True)
    for name in intent.unlocks:
        brief = _set_slot(brief, name, None, False)
    return replace(research, brief=brief, updated_at=now)


def next_question(research: Research) -> DialoguePrompt:
    if all_slots_locked(research.brief):
        return DialoguePrompt(None, "五项研究设定已锁定，请检查确认开跑卡。")
    for name in SlotName:
        slot = getattr(research.brief, name.value)
        if slot.value is None or not slot.locked:
            return DialoguePrompt(name, QUESTIONS[name])
    raise AssertionError("unreachable slot state")
```

- [ ] **Step 4: Run the dialogue suite and verify GREEN**

Run: `python -m pytest tests/test_dialogue.py -q && python -m mypy engine/dialogue`

Expected: PASS with `4 passed`; mypy exits `0`.

- [ ] **Step 5: Commit purposeful slot collection**

```bash
git add engine/dialogue tests/test_dialogue.py
git commit -m "feat(engine): add five-slot dialogue"
```

### Task 4: Public-Material Gathering, Data Adapters, and Locked Specification

**Files:**
- Create: `engine/research/gather.py`
- Create: `engine/research/specify.py`
- Create: `materials/README.md`
- Test: `tests/test_gather_specify.py`

**Interfaces:**
- Consumes: `Research`, `Universe`, `MethodRef`, `ChangeClass`, `StrategySpec`, `MarketPanel`
- Produces: `MaterialPort.fetch(self, query: str) -> tuple[Material, ...]`; `DataPort.load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame`; `gather(query: str, ports: tuple[MaterialPort, ...]) -> tuple[Material, ...]`; `propose_brief_updates(message: str, materials: tuple[Material, ...], profile: DataProfile) -> BriefProposal`; `classify_change(change: ProposedChange) -> ChangeClass`; `specify(research: Research, prior: StrategySpec | None, proposal: ModelProposal) -> StrategySpec`

- [ ] **Step 1: Write failing adapter, proposal, classifier, and invariant tests**

Create `tests/test_gather_specify.py`:

```python
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from engine.research.gather import DataProfile, Material, MaterialPort, gather
from engine.research.models import (
    AssetClass,
    ChangeClass,
    CoverageFloor,
    Market,
    MethodRef,
    ResearchBrief,
    Slot,
    Universe,
    new_research,
)
from engine.research.specify import (
    ModelProposal,
    ProposedChange,
    classify_change,
    propose_brief_updates,
    specify,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


class FakeMaterials(MaterialPort):
    def __init__(self, source: str) -> None:
        self.source = source

    def fetch(self, query: str) -> tuple[Material, ...]:
        return (
            Material(
                material_id=f"{self.source}-1",
                source=self.source,
                title=f"{query} factor evidence",
                url=f"https://example.test/{self.source}",
                text="Low-volatility reversal should be tested out of sample and for crowding.",
                fetched_at=NOW,
            ),
        )


def locked_research():
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAPL", "MSFT"))
    brief = ResearchBrief(
        thesis=Slot("美股低波动回归", True),
        universe=Slot(universe, True),
        max_effective_hours=Slot(12.0, True),
        round1_methods=Slot(
            (
                MethodRef("overfit.walk", "walk-v1"),
                MethodRef("stability.oos", "stability-v1"),
                MethodRef("crowding.load", "crowding-v1"),
                MethodRef("cost.turnover", "cost-v1"),
            ),
            True,
        ),
        coverage_floor=Slot(CoverageFloor(2, 10, 5.0), True),
    )
    return replace(new_research("r-spec", NOW), brief=brief)


def test_gather_keeps_public_source_provenance() -> None:
    result = gather("美股低波动回归", (FakeMaterials("papers"), FakeMaterials("sec-edgar")))
    assert [item.source for item in result] == ["papers", "sec-edgar"]
    assert all(item.url.startswith("https://") for item in result)


def test_materials_and_data_profile_propose_values_without_locking() -> None:
    materials = gather("美股低波动回归", (FakeMaterials("papers"),))
    proposal = propose_brief_updates(
        "美股低波动回归",
        materials,
        DataProfile(symbols=("AAPL", "MSFT"), years=12, missing_pct=1.5),
    )
    assert proposal.universe.market is Market.US
    assert proposal.universe.asset_class is AssetClass.EQUITY
    assert [item.method_id for item in proposal.round1_methods] == [
        "overfit.walk",
        "stability.oos",
        "crowding.load",
        "cost.turnover",
    ]
    assert proposal.coverage_floor == CoverageFloor(2, 12, 1.5)
    assert proposal.locked is False


@pytest.mark.parametrize(
    ("change", "expected"),
    (
        (ProposedChange("lookback_days", 20, 30), ChangeClass.PARAM),
        (ProposedChange("signal_definition", "zscore", "rank"), ChangeClass.MODEL),
        (ProposedChange("thesis_locked", "reversion", "momentum"), ChangeClass.ECONOMIC),
        (ProposedChange("universe", "US equity", "CN equity"), ChangeClass.ECONOMIC),
        (ProposedChange("method_set", "walk-v1", "walk-v2"), ChangeClass.ECONOMIC),
        (ProposedChange("max_drawdown_floor", -0.25, -0.30), ChangeClass.ECONOMIC),
        (ProposedChange("available_assets", 50, 40, breaches_coverage=True), ChangeClass.COVERAGE),
    ),
)
def test_change_classifier(change: ProposedChange, expected: ChangeClass) -> None:
    assert classify_change(change) is expected


def test_specify_preserves_locked_thesis_universe_and_methods() -> None:
    research = locked_research()
    first = specify(research, None, ModelProposal("mean_reversion", 20, 1.0, "long_only"))
    second = specify(research, first, ModelProposal("mean_reversion", 30, 0.8, "long_only"))
    assert second.thesis_locked == first.thesis_locked
    assert second.universe == first.universe
    assert second.method_set == first.method_set
    assert second.lookback_days == 30


def test_specify_rejects_a_prior_spec_from_another_economic_version() -> None:
    research = locked_research()
    first = specify(research, None, ModelProposal("mean_reversion", 20, 1.0, "long_only"))
    foreign = replace(first, thesis_locked="momentum")
    with pytest.raises(ValueError, match="locked strategy identity"):
        specify(research, foreign, ModelProposal("mean_reversion", 30, 0.8, "long_only"))
```

- [ ] **Step 2: Run the gather/specify test and verify RED**

Run: `python -m pytest tests/test_gather_specify.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'engine.research.gather'`.

- [ ] **Step 3: Implement public/local adapters, market-data ports, proposal enrichment, and specification guards**

Create `engine/research/gather.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Protocol

import akshare as ak
import httpx
import pandas as pd
import yfinance as yf


@dataclass(frozen=True, slots=True)
class Material:
    material_id: str
    source: str
    title: str
    url: str
    text: str
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class DataProfile:
    symbols: tuple[str, ...]
    years: int
    missing_pct: float


class MaterialPort(Protocol):
    def fetch(self, query: str) -> tuple[Material, ...]:
        raise NotImplementedError


class DataPort(Protocol):
    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        raise NotImplementedError


@dataclass(slots=True)
class PapersAdapter:
    client: httpx.Client
    now: Callable[[], datetime]

    def fetch(self, query: str) -> tuple[Material, ...]:
        response = self.client.get(
            "https://api.crossref.org/works",
            params={"query": query, "rows": 5, "select": "DOI,title,URL,abstract"},
            timeout=20.0,
        )
        response.raise_for_status()
        result = []
        for item in response.json()["message"]["items"]:
            title = " ".join(item.get("title", ["Untitled"]))
            result.append(
                Material(
                    material_id=f"doi:{item['DOI']}",
                    source="papers",
                    title=title,
                    url=item.get("URL", f"https://doi.org/{item['DOI']}"),
                    text=item.get("abstract", title),
                    fetched_at=self.now(),
                )
            )
        return tuple(result)


@dataclass(slots=True)
class SecEdgarAdapter:
    client: httpx.Client
    now: Callable[[], datetime]
    user_agent: str

    def fetch(self, query: str) -> tuple[Material, ...]:
        response = self.client.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": self.user_agent},
            timeout=20.0,
        )
        response.raise_for_status()
        matches = []
        for item in response.json().values():
            haystack = f"{item['ticker']} {item['title']}".lower()
            if query.lower() in haystack:
                cik = str(item["cik_str"]).zfill(10)
                matches.append(
                    Material(
                        material_id=f"sec:{cik}",
                        source="sec-edgar",
                        title=f"{item['ticker']} — {item['title']}",
                        url=f"https://data.sec.gov/submissions/CIK{cik}.json",
                        text=f"EDGAR issuer record for {item['title']}",
                        fetched_at=self.now(),
                    )
                )
        return tuple(matches[:5])


@dataclass(frozen=True, slots=True)
class LocalMaterialAdapter:
    root: Path
    now: Callable[[], datetime]

    def fetch(self, query: str) -> tuple[Material, ...]:
        words = {word.lower() for word in query.split() if word}
        result = []
        for path in sorted(self.root.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if not words or any(word in text.lower() for word in words):
                result.append(
                    Material(
                        material_id=f"local:{path.name}",
                        source="local",
                        title=path.stem,
                        url=path.resolve().as_uri(),
                        text=text,
                        fetched_at=self.now(),
                    )
                )
        return tuple(result)


class YahooDataAdapter:
    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        provider_symbols = ["^GSPC" if symbol == "SPX" else symbol for symbol in symbols]
        frame = yf.download(
            provider_symbols,
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=True,
            progress=False,
        )
        close = frame["Close"] if "Close" in frame else frame
        if len(symbols) == 1:
            close = close.to_frame(name=symbols[0]) if isinstance(close, pd.Series) else close
            close.columns = [symbols[0]]
        else:
            close = close.rename(columns={"^GSPC": "SPX"})
        return close.rename_axis("date").sort_index()


class AkShareDataAdapter:
    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        columns: dict[str, pd.Series] = {}
        for symbol in symbols:
            if symbol == "CBA00101.CS":
                raw = ak.bond_new_composite_index_cbond(indicator="财富", period="总值")
                series = pd.Series(
                    raw["value"].to_numpy(),
                    index=pd.to_datetime(raw["date"]),
                    name=symbol,
                )
            elif symbol.startswith("CN_BOND:"):
                provider_symbol = symbol.removeprefix("CN_BOND:")
                raw = ak.bond_zh_hs_daily(symbol=provider_symbol)
                series = pd.Series(
                    raw["close"].to_numpy(),
                    index=pd.to_datetime(raw["date"]),
                    name=symbol,
                )
            elif symbol.startswith("CN_FUND:"):
                provider_symbol = symbol.removeprefix("CN_FUND:")
                raw = ak.fund_etf_hist_em(
                    symbol=provider_symbol,
                    period="daily",
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                    adjust="qfq",
                )
                series = pd.Series(
                    raw["收盘"].to_numpy(),
                    index=pd.to_datetime(raw["日期"]),
                    name=symbol,
                )
            elif symbol == "000300.SH":
                raw = ak.stock_zh_index_daily_em(symbol="sh000300")
                series = pd.Series(
                    raw["close"].to_numpy(),
                    index=pd.to_datetime(raw["date"]),
                    name=symbol,
                )
            else:
                provider_symbol = symbol.split(".")[0]
                raw = ak.stock_zh_a_hist(
                    symbol=provider_symbol,
                    period="daily",
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                    adjust="qfq",
                )
                series = pd.Series(
                    raw["收盘"].to_numpy(),
                    index=pd.to_datetime(raw["日期"]),
                    name=symbol,
                )
            columns[symbol] = series.loc[start.isoformat() : end.isoformat()]
        return pd.DataFrame(columns).sort_index()


@dataclass(frozen=True, slots=True)
class RoutingDataAdapter:
    yahoo: YahooDataAdapter
    akshare: AkShareDataAdapter

    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        is_cn = all(
            symbol == "CBA00101.CS"
            or symbol.startswith(("CN_BOND:", "CN_FUND:"))
            or symbol.endswith((".SH", ".SZ"))
            for symbol in symbols
        )
        return (
            self.akshare.load_daily(symbols, start, end)
            if is_cn
            else self.yahoo.load_daily(symbols, start, end)
        )


def gather(query: str, ports: tuple[MaterialPort, ...]) -> tuple[Material, ...]:
    materials = tuple(item for port in ports for item in port.fetch(query))
    seen: set[str] = set()
    unique = []
    for item in materials:
        if item.material_id not in seen:
            seen.add(item.material_id)
            unique.append(item)
    return tuple(unique)
```

Create `engine/research/specify.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from engine.research.gather import DataProfile, Material
from engine.research.models import (
    AssetClass,
    ChangeClass,
    CoverageFloor,
    Market,
    MethodRef,
    Research,
    Universe,
)
from engine.strategy import Side, StrategySpec


@dataclass(frozen=True, slots=True)
class BriefProposal:
    thesis: str
    universe: Universe
    round1_methods: tuple[MethodRef, ...]
    coverage_floor: CoverageFloor
    evidence_ids: tuple[str, ...]
    locked: bool = False


@dataclass(frozen=True, slots=True)
class ProposedChange:
    field: str
    before: object
    after: object
    breaches_coverage: bool = False


@dataclass(frozen=True, slots=True)
class ModelProposal:
    model_family: str
    lookback_days: int
    entry_z: float
    side: Side = "long_only"


def propose_brief_updates(
    message: str,
    materials: tuple[Material, ...],
    profile: DataProfile,
) -> BriefProposal:
    market = Market.US if "美股" in message or "美国" in message else Market.CN
    asset = AssetClass.BOND if "债" in message else AssetClass.EQUITY
    methods = (
        MethodRef("overfit.walk", "walk-v1"),
        MethodRef("stability.oos", "stability-v1"),
        MethodRef("crowding.load", "crowding-v1"),
        MethodRef("cost.turnover", "cost-v1"),
    )
    return BriefProposal(
        thesis=message.strip(),
        universe=Universe(market, asset, asset, profile.symbols),
        round1_methods=methods,
        coverage_floor=CoverageFloor(
            min_assets=len(profile.symbols),
            min_years=profile.years,
            max_missing_pct=profile.missing_pct,
        ),
        evidence_ids=tuple(item.material_id for item in materials),
    )


def classify_change(change: ProposedChange) -> ChangeClass:
    if change.breaches_coverage:
        return ChangeClass.COVERAGE
    if change.field in {
        "thesis_locked",
        "universe",
        "method_set",
        "max_drawdown_floor",
        "validation_thresholds",
    }:
        return ChangeClass.ECONOMIC
    if change.field in {"model_family", "signal_definition", "feature_set"}:
        return ChangeClass.MODEL
    return ChangeClass.PARAM


def specify(
    research: Research,
    prior: StrategySpec | None,
    proposal: ModelProposal,
) -> StrategySpec:
    thesis = research.brief.thesis.value
    universe = research.brief.universe.value
    methods = research.brief.round1_methods.value
    if thesis is None or universe is None or methods is None:
        raise ValueError("thesis, universe, and method set must be present")
    if prior is not None and (
        prior.thesis_locked != thesis
        or prior.universe != universe
        or prior.method_set != methods
    ):
        raise ValueError("prior spec does not match locked strategy identity")
    return StrategySpec(
        id=f"{research.research_id}-{proposal.model_family}",
        thesis_locked=thesis,
        universe=universe,
        frequency="1d",
        side=proposal.side,
        method_set=methods,
        model_family=proposal.model_family,
        lookback_days=proposal.lookback_days,
        entry_z=proposal.entry_z,
        max_drawdown_floor=prior.max_drawdown_floor if prior else -0.25,
    )
```

Create `materials/README.md`:

```markdown
# Local research materials

Place user-provided Markdown sources in this directory. Gathered public sources are saved with
their URL, fetch time, and content hash. Strategy packs freeze the records actually used.
```

- [ ] **Step 4: Run the gather/specify suite and verify GREEN**

Run: `python -m pytest tests/test_gather_specify.py -q && python -m mypy engine/research/gather.py engine/research/specify.py`

Expected: PASS with `11 passed`; mypy exits `0`.

- [ ] **Step 5: Commit gathering and specification**

```bash
git add engine/research/gather.py engine/research/specify.py materials/README.md tests/test_gather_specify.py
git commit -m "feat(engine): gather evidence and lock strategy specs"
```

### Task 5: Daily Simulation and Benchmark Metrics

**Files:**
- Create: `engine/metrics.py`
- Create: `engine/research/simulate.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: `AlphaStrategy`, `StrategySpec`, `MarketPanel`, `run_daily_backtest`, `DataPort.load_daily(...)`
- Produces: `benchmark_for(universe: Universe) -> BenchmarkSpec`; `calculate_metrics(strategy_returns: pd.Series, benchmark_returns: pd.Series, benchmark_id: str, diagnostics: SimulationDiagnostics) -> SimulationReport`; `simulate_daily(strategy: AlphaStrategy, data_port: DataPort, start: date, end: date, *, snapshot_path: Path | None = None) -> SimulationReport`; `SimulationReport` with required `r_total`, `r_ann`, `sharpe`, `vol_ann`, `max_drawdown`, `benchmark_id`, `r_bench_ann`, `excess_ann`, `tracking_error`, `information_ratio`

- [ ] **Step 1: Write the failing benchmark and metrics tests**

Create `tests/test_metrics.py`:

```python
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from engine.metrics import (
    SimulationDiagnostics,
    benchmark_for,
    calculate_metrics,
)
from engine.research.models import AssetClass, Market, Universe
from engine.research.simulate import simulate_daily
from engine.strategy import MarketPanel, MeanReversionStrategy, StrategySpec


@pytest.mark.parametrize(
    ("universe", "expected"),
    (
        (Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("A",)), "SPX"),
        (Universe(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY, ("A",)), "000300.SH"),
        (Universe(Market.US, AssetClass.BOND, AssetClass.BOND, ("B",)), "AGG"),
        (Universe(Market.CN, AssetClass.BOND, AssetClass.BOND, ("B",)), "CBA00101.CS"),
        (Universe(Market.US, AssetClass.FUND, AssetClass.EQUITY, ("F",)), "SPX"),
        (Universe(Market.CN, AssetClass.FUND, AssetClass.BOND, ("F",)), "CBA00101.CS"),
    ),
)
def test_benchmark_is_selected_by_market_and_underlying_asset(
    universe: Universe,
    expected: str,
) -> None:
    assert benchmark_for(universe).benchmark_id == expected


def test_required_metrics_are_compounded_and_finite() -> None:
    index = pd.date_range("2026-01-01", periods=4, tz=UTC)
    strategy = pd.Series([0.10, -0.05, 0.02, 0.01], index=index)
    benchmark = pd.Series([0.04, -0.01, 0.01, 0.00], index=index)
    diagnostics = SimulationDiagnostics(
        sharpe_oos=0.8,
        sharpe_is=1.0,
        oos_segment_returns=(0.02, 0.03, 0.01),
        top_20_crowding_sharpe_impact=0.05,
        annual_turnover=1.0,
        covered_assets=2,
        missing_pct=0.0,
    )

    report = calculate_metrics(strategy, benchmark, "SPX", diagnostics)

    assert report.r_total == pytest.approx((1.10 * 0.95 * 1.02 * 1.01) - 1)
    assert report.benchmark_id == "SPX"
    assert report.r_ann > report.r_bench_ann
    assert report.excess_ann == pytest.approx(report.r_ann - report.r_bench_ann)
    assert report.vol_ann > 0
    assert report.max_drawdown == pytest.approx(-0.05)
    assert report.tracking_error > 0
    assert report.information_ratio == pytest.approx(
        report.excess_ann / report.tracking_error
    )


class FakeData:
    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        index = pd.date_range(start, periods=40, tz=UTC)
        return pd.DataFrame(
            {symbol: [100.0 + day + offset for day in range(40)] for offset, symbol in enumerate(symbols)},
            index=index,
        )


def test_daily_simulation_fetches_strategy_and_benchmark() -> None:
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA", "BBB"))
    strategy = MeanReversionStrategy(
        StrategySpec(
            id="s-1",
            thesis_locked="reversal",
            universe=universe,
            frequency="1d",
            side="long_only",
            method_set=(),
            model_family="mean_reversion",
            lookback_days=2,
            entry_z=0.5,
        )
    )
    report = simulate_daily(strategy, FakeData(), date(2025, 1, 1), date(2026, 1, 1))
    assert report.benchmark_id == "SPX"
    assert report.observations == 40
```

- [ ] **Step 2: Run the metrics test and verify RED**

Run: `python -m pytest tests/test_metrics.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'engine.metrics'`.

- [ ] **Step 3: Implement benchmark resolution, daily simulation, and every required scorecard field**

Create `engine/metrics.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

from engine.research.models import AssetClass, Market, Universe

TRADING_DAYS = 252


@dataclass(frozen=True, slots=True)
class BenchmarkSpec:
    benchmark_id: str
    name: str
    return_kind: str


BENCHMARKS = {
    (Market.US, AssetClass.EQUITY): BenchmarkSpec("SPX", "S&P 500", "price_index"),
    (Market.CN, AssetClass.EQUITY): BenchmarkSpec("000300.SH", "CSI 300", "price_index"),
    (Market.US, AssetClass.BOND): BenchmarkSpec("AGG", "Bloomberg US Agg ETF proxy", "total_return_proxy"),
    (Market.CN, AssetClass.BOND): BenchmarkSpec(
        "CBA00101.CS",
        "ChinaBond New Composite Wealth Index",
        "wealth_index",
    ),
}


@dataclass(frozen=True, slots=True)
class SimulationDiagnostics:
    sharpe_oos: float
    sharpe_is: float
    oos_segment_returns: tuple[float, ...]
    top_20_crowding_sharpe_impact: float
    annual_turnover: float
    covered_assets: int
    missing_pct: float


@dataclass(frozen=True, slots=True)
class SimulationReport:
    r_total: float
    r_ann: float
    sharpe: float
    vol_ann: float
    max_drawdown: float
    benchmark_id: str
    r_bench_ann: float
    excess_ann: float
    tracking_error: float
    information_ratio: float
    sharpe_oos: float
    sharpe_is: float
    oos_segment_returns: tuple[float, ...]
    top_20_crowding_sharpe_impact: float
    annual_turnover: float
    observations: int
    covered_assets: int
    missing_pct: float


def benchmark_for(universe: Universe) -> BenchmarkSpec:
    return BENCHMARKS[(universe.market, universe.underlying_asset_class)]


def _annualized_return(returns: pd.Series) -> float:
    total = float((1.0 + returns).prod() - 1.0)
    return float((1.0 + total) ** (TRADING_DAYS / len(returns)) - 1.0)


def _ratio(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0.0 else numerator / denominator


def calculate_metrics(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    benchmark_id: str,
    diagnostics: SimulationDiagnostics,
) -> SimulationReport:
    aligned = pd.concat(
        [strategy_returns.rename("strategy"), benchmark_returns.rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna()
    if aligned.empty or not np.isfinite(aligned.to_numpy()).all():
        raise ValueError("strategy and benchmark need finite overlapping daily returns")
    strategy = aligned["strategy"]
    benchmark = aligned["benchmark"]
    r_total = float((1.0 + strategy).prod() - 1.0)
    r_ann = _annualized_return(strategy)
    r_bench_ann = _annualized_return(benchmark)
    vol_ann = float(strategy.std(ddof=1) * sqrt(TRADING_DAYS))
    sharpe = _ratio(float(strategy.mean() * TRADING_DAYS), vol_ann)
    wealth = (1.0 + strategy).cumprod()
    max_drawdown = float((wealth / wealth.cummax() - 1.0).min())
    tracking_error = float((strategy - benchmark).std(ddof=1) * sqrt(TRADING_DAYS))
    excess_ann = r_ann - r_bench_ann
    return SimulationReport(
        r_total=r_total,
        r_ann=r_ann,
        sharpe=sharpe,
        vol_ann=vol_ann,
        max_drawdown=max_drawdown,
        benchmark_id=benchmark_id,
        r_bench_ann=r_bench_ann,
        excess_ann=excess_ann,
        tracking_error=tracking_error,
        information_ratio=_ratio(excess_ann, tracking_error),
        sharpe_oos=diagnostics.sharpe_oos,
        sharpe_is=diagnostics.sharpe_is,
        oos_segment_returns=diagnostics.oos_segment_returns,
        top_20_crowding_sharpe_impact=diagnostics.top_20_crowding_sharpe_impact,
        annual_turnover=diagnostics.annual_turnover,
        observations=len(aligned),
        covered_assets=diagnostics.covered_assets,
        missing_pct=diagnostics.missing_pct,
    )
```

Create `engine/research/simulate.py`:

```python
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from engine.metrics import (
    SimulationDiagnostics,
    SimulationReport,
    benchmark_for,
    calculate_metrics,
)
from engine.research.gather import DataPort
from engine.strategy import AlphaStrategy, MarketPanel, run_daily_backtest


def simulate_daily(
    strategy: AlphaStrategy,
    data_port: DataPort,
    start: date,
    end: date,
    *,
    snapshot_path: Path | None = None,
) -> SimulationReport:
    benchmark = benchmark_for(strategy.universe)
    symbols = strategy.universe.symbols
    prices = data_port.load_daily(symbols, start, end)
    benchmark_prices = data_port.load_daily((benchmark.benchmark_id,), start, end)
    if snapshot_path is not None:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = prices.copy()
        snapshot["__benchmark__"] = benchmark_prices[benchmark.benchmark_id].reindex(
            snapshot.index
        )
        snapshot.to_csv(snapshot_path, index_label="date")
    panel = MarketPanel(
        prices,
        datetime.now(UTC),
        benchmark_prices[benchmark.benchmark_id],
    )
    strategy_returns = run_daily_backtest(strategy, panel)
    benchmark_returns = benchmark_prices[benchmark.benchmark_id].pct_change(fill_method=None).fillna(0.0)

    def sharpe(values: pd.Series) -> float:
        std = float(values.std(ddof=1))
        return 0.0 if std == 0.0 else float(values.mean() / std * (252**0.5))

    split_points = np.linspace(0, len(strategy_returns), 7, dtype=int)
    in_sample_sharpes = []
    out_sample_sharpes = []
    segment_returns = []
    for split in range(1, 6):
        train = strategy_returns.iloc[: split_points[split]]
        test = strategy_returns.iloc[split_points[split] : split_points[split + 1]]
        in_sample_sharpes.append(sharpe(train))
        out_sample_sharpes.append(sharpe(test))
        segment_returns.append(float((1.0 + test).prod() - 1.0))
    raw_signals = strategy.generate_signals(panel).shift(1).fillna(0.0)
    gross = raw_signals.abs().sum(axis=1).replace(0.0, 1.0)
    weights = raw_signals.div(gross, axis=0)
    concentration = weights.abs().max(axis=1)
    crowded = strategy_returns[concentration >= concentration.quantile(0.8)]
    diagnostics = SimulationDiagnostics(
        sharpe_oos=float(np.mean(out_sample_sharpes)),
        sharpe_is=float(np.mean(in_sample_sharpes)),
        oos_segment_returns=tuple(segment_returns),
        top_20_crowding_sharpe_impact=sharpe(crowded),
        annual_turnover=float(weights.diff().abs().sum().sum() / len(prices) * 252),
        covered_assets=int(prices.notna().any(axis=0).sum()),
        missing_pct=float(prices.isna().to_numpy().mean() * 100),
    )
    return calculate_metrics(
        strategy_returns,
        benchmark_returns,
        benchmark.benchmark_id,
        diagnostics,
    )
```

- [ ] **Step 4: Run the simulation metrics suite and verify GREEN**

Run: `python -m pytest tests/test_metrics.py -q && python -m mypy engine/metrics.py engine/research/simulate.py`

Expected: PASS with `8 passed`; mypy exits `0`.

- [ ] **Step 5: Commit benchmarked simulation**

```bash
git add engine/metrics.py engine/research/simulate.py tests/test_metrics.py
git commit -m "feat(engine): score daily simulations against benchmarks"
```

### Task 6: Primary Scorecard and Four Frozen Verifiers

**Files:**
- Create: `engine/verifiers.py`
- Test: `tests/test_verifiers.py`

**Interfaces:**
- Consumes: `SimulationReport`, `StrategySpec`, `Market`
- Produces: `run_verifiers(report: SimulationReport, spec: StrategySpec) -> VerificationReport`; `VerifierResult`; `VerificationReport.passed: bool`; immutable `VERIFIER_REVISIONS`

- [ ] **Step 1: Write the failing primary and additional-gate tests**

Create `tests/test_verifiers.py`:

```python
from dataclasses import replace

import pytest

from engine.metrics import SimulationReport
from engine.research.models import AssetClass, Market, Universe
from engine.strategy import StrategySpec
from engine.verifiers import VERIFIER_REVISIONS, run_verifiers


def spec(market: Market = Market.US) -> StrategySpec:
    universe = Universe(market, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA",))
    return StrategySpec(
        id="s-verify",
        thesis_locked="reversal",
        universe=universe,
        frequency="1d",
        side="long_only",
        method_set=(),
        model_family="mean_reversion",
        lookback_days=20,
        entry_z=1.0,
        max_drawdown_floor=-0.25,
    )


def passing_report() -> SimulationReport:
    return SimulationReport(
        r_total=0.20,
        r_ann=0.12,
        sharpe=0.9,
        vol_ann=0.13,
        max_drawdown=-0.20,
        benchmark_id="SPX",
        r_bench_ann=0.08,
        excess_ann=0.04,
        tracking_error=0.06,
        information_ratio=2 / 3,
        sharpe_oos=0.7,
        sharpe_is=1.0,
        oos_segment_returns=(0.02, 0.01, -0.005),
        top_20_crowding_sharpe_impact=0.01,
        annual_turnover=1.0,
        observations=756,
        covered_assets=1,
        missing_pct=0.0,
    )


def test_primary_scorecard_and_all_four_verifiers_pass() -> None:
    result = run_verifiers(passing_report(), spec())
    assert [gate.verifier_id for gate in result.results] == [
        "scorecard.market",
        "overfit.walk",
        "stability.oos",
        "crowding.load",
        "cost.turnover",
    ]
    assert result.passed


@pytest.mark.parametrize(
    ("field", "value", "failed"),
    (
        ("sharpe_oos", 0.0, "scorecard.market"),
        ("excess_ann", 0.0, "scorecard.market"),
        ("max_drawdown", -0.26, "scorecard.market"),
        ("sharpe_oos", 0.5, "overfit.walk"),
        ("oos_segment_returns", (0.01, -0.01, 0.0), "stability.oos"),
        ("top_20_crowding_sharpe_impact", -0.01, "crowding.load"),
        ("annual_turnover", 50.0, "cost.turnover"),
    ),
)
def test_each_locked_gate_can_fail(field: str, value: object, failed: str) -> None:
    result = run_verifiers(replace(passing_report(), **{field: value}), spec())
    assert failed in {gate.verifier_id for gate in result.results if not gate.passed}
    assert not result.passed


def test_costs_are_10bp_us_and_20bp_cn() -> None:
    assert VERIFIER_REVISIONS["overfit.walk"]["n_splits"] == 5
    assert VERIFIER_REVISIONS["cost.turnover"]["us_cost_bp"] == 10
    assert VERIFIER_REVISIONS["cost.turnover"]["cn_cost_bp"] == 20
    us = run_verifiers(passing_report(), spec(Market.US))
    cn = run_verifiers(passing_report(), spec(Market.CN))
    us_cost = next(item for item in us.results if item.verifier_id == "cost.turnover")
    cn_cost = next(item for item in cn.results if item.verifier_id == "cost.turnover")
    assert us_cost.values["cost_drag"] == pytest.approx(0.001)
    assert cn_cost.values["cost_drag"] == pytest.approx(0.002)
```

- [ ] **Step 2: Run the verifier test and verify RED**

Run: `python -m pytest tests/test_verifiers.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'engine.verifiers'`.

- [ ] **Step 3: Implement the benchmark-primary scorecard and four additional gates**

Create `engine/verifiers.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from engine.metrics import SimulationReport
from engine.research.models import Market
from engine.strategy import StrategySpec

VERIFIER_REVISIONS = MappingProxyType(
    {
        "scorecard.market": {
            "revision": "scorecard-v1",
            "sharpe_oos_min_exclusive": 0.0,
            "excess_ann_min_exclusive": 0.0,
            "default_max_drawdown_floor": -0.25,
        },
        "overfit.walk": {
            "revision": "walk-v1",
            "n_splits": 5,
            "oos_to_is_min": 0.6,
            "sharpe_oos_min_exclusive": 0.0,
        },
        "stability.oos": {
            "revision": "stability-v1",
            "segments_min": 3,
            "same_sign_ratio_min": 2 / 3,
        },
        "crowding.load": {
            "revision": "crowding-v1",
            "top_bucket_pct": 20,
            "sharpe_impact_min": 0.0,
        },
        "cost.turnover": {
            "revision": "cost-v1",
            "us_cost_bp": 10,
            "cn_cost_bp": 20,
            "net_excess_min_exclusive": 0.0,
        },
    }
)


@dataclass(frozen=True, slots=True)
class VerifierResult:
    verifier_id: str
    revision: str
    passed: bool
    values: Mapping[str, float]
    rule: str


@dataclass(frozen=True, slots=True)
class VerificationReport:
    results: tuple[VerifierResult, ...]

    @property
    def passed(self) -> bool:
        return len(self.results) == 5 and all(result.passed for result in self.results)


def run_verifiers(report: SimulationReport, spec: StrategySpec) -> VerificationReport:
    scorecard = VerifierResult(
        "scorecard.market",
        "scorecard-v1",
        report.sharpe_oos > 0
        and report.excess_ann > 0
        and report.max_drawdown >= spec.max_drawdown_floor,
        {
            "sharpe_oos": report.sharpe_oos,
            "excess_ann": report.excess_ann,
            "max_drawdown": report.max_drawdown,
            "max_drawdown_floor": spec.max_drawdown_floor,
        },
        "sharpe_oos > 0 and excess_ann > 0 and max_drawdown >= max_drawdown_floor",
    )
    ratio = 0.0 if report.sharpe_is == 0.0 else report.sharpe_oos / report.sharpe_is
    walk = VerifierResult(
        "overfit.walk",
        "walk-v1",
        report.sharpe_oos > 0 and ratio >= 0.6,
        {"sharpe_oos": report.sharpe_oos, "oos_to_is": ratio},
        "sharpe_oos > 0 and sharpe_oos / sharpe_is >= 0.6",
    )
    segments = report.oos_segment_returns
    sign = lambda value: (value > 0) - (value < 0)
    first_sign = sign(segments[0]) if segments else 0
    same_sign_ratio = (
        sum(sign(value) == first_sign for value in segments) / len(segments)
        if segments
        else 0.0
    )
    stability = VerifierResult(
        "stability.oos",
        "stability-v1",
        len(segments) >= 3 and same_sign_ratio >= 2 / 3,
        {"segments": float(len(segments)), "same_sign_ratio": same_sign_ratio},
        "at least 3 OOS segments and same-sign ratio >= 2/3",
    )
    crowding = VerifierResult(
        "crowding.load",
        "crowding-v1",
        report.top_20_crowding_sharpe_impact >= 0,
        {"top_20_crowding_sharpe_impact": report.top_20_crowding_sharpe_impact},
        "top 20% crowding bucket sharpe impact >= 0",
    )
    cost_bp = 10 if spec.universe.market is Market.US else 20
    cost_drag = report.annual_turnover * cost_bp / 10_000
    net_excess = report.excess_ann - cost_drag
    cost = VerifierResult(
        "cost.turnover",
        "cost-v1",
        net_excess > 0,
        {"cost_drag": cost_drag, "net_excess_ann": net_excess},
        "excess_ann - annual_turnover * market_cost_bp / 10000 > 0",
    )
    return VerificationReport((scorecard, walk, stability, crowding, cost))
```

- [ ] **Step 4: Run the verifier suite and verify GREEN**

Run: `python -m pytest tests/test_verifiers.py -q && python -m mypy engine/verifiers.py`

Expected: PASS with `9 passed`; mypy exits `0`.

- [ ] **Step 5: Commit frozen verification gates**

```bash
git add engine/verifiers.py tests/test_verifiers.py
git commit -m "feat(engine): enforce benchmark and robustness gates"
```

### Task 7: Mandatory Frozen-Rubric Subagent Review Gate

**Files:**
- Create: `engine/review/__init__.py`
- Create: `engine/review/subagent.py`
- Test: `tests/test_reviewer.py`

**Interfaces:**
- Consumes: `RoundDraft`, `Attempt`, `Round`, `ReviewReport`, `ReviewFinding`, `ConfirmRequest`, `ConfirmKind`
- Produces: `ReviewerPort.run(self, round_draft: RoundDraft) -> ReviewReport`; `LLMPort.complete(self, system: str, user: str) -> str`; `OpenAICompatibleLLM`; `SubagentReviewer`; `run_review_gate(initial: RoundDraft, reviewer: ReviewerPort, retry: RetryFactory, now: datetime, prior_failures: int = 0, on_attempt: AttemptSink | None = None) -> ReviewGateOutcome`; `FROZEN_REVIEW_RUBRIC`; `MAX_CONSECUTIVE_REVIEW_FAILURES = 3`

- [ ] **Step 1: Write the failing strict-result, retry, pass, and cap tests**

Create `tests/test_reviewer.py`:

```python
from datetime import UTC, datetime

from engine.research.models import (
    AssetClass,
    Attempt,
    ChangeClass,
    Market,
    RoundDraft,
    Universe,
)
from engine.review.subagent import (
    FROZEN_REVIEW_RUBRIC,
    MAX_CONSECUTIVE_REVIEW_FAILURES,
    LLMPort,
    ReviewerPort,
    SubagentReviewer,
    run_review_gate,
)
from engine.strategy import StrategySpec
from engine.verifiers import VerificationReport

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


class SequenceLLM(LLMPort):
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.responses.pop(0)


def draft(number: int = 1) -> RoundDraft:
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA",))
    spec = StrategySpec(
        id=f"s-{number}",
        thesis_locked="reversal",
        universe=universe,
        frequency="1d",
        side="long_only",
        method_set=(),
        model_family="mean_reversion",
        lookback_days=20 + number,
        entry_z=1.0,
    )
    attempt = Attempt(
        attempt_id=f"a-{number}",
        number=number,
        change_class=ChangeClass.PARAM,
        spec=spec,
        simulation=object(),
        verification=VerificationReport(()),
        review=object(),
    )
    return RoundDraft(version_number=1, round_number=1, attempt=attempt)


def test_frozen_rubric_names_all_non_negotiable_checks() -> None:
    assert "lookahead bias" in FROZEN_REVIEW_RUBRIC
    assert "economic-logic drift" in FROZEN_REVIEW_RUBRIC
    assert "data-snooping" in FROZEN_REVIEW_RUBRIC
    assert "benchmark mismatch" in FROZEN_REVIEW_RUBRIC


def test_second_llm_result_has_exact_review_shape() -> None:
    llm = SequenceLLM(
        ['{"passed":false,"findings":[{"code":"lookahead","message":"future data"}],'
         '"required_changes":"lag the signal"}']
    )
    report = SubagentReviewer(llm).run(draft())
    assert report.passed is False
    assert report.findings[0].code == "lookahead"
    assert report.required_changes == "lag the signal"
    assert llm.calls[0][0] == FROZEN_REVIEW_RUBRIC


def test_a_passed_retry_creates_one_round_under_same_version() -> None:
    llm = SequenceLLM(
        [
            '{"passed":false,"findings":[{"code":"snoop","message":"tuned on OOS"}],'
            '"required_changes":"freeze OOS"}',
            '{"passed":true,"findings":[]}',
        ]
    )
    reviewer = SubagentReviewer(llm)

    outcome = run_review_gate(
        draft(),
        reviewer,
        lambda prior, report: draft(prior.attempt.number + 1),
        NOW,
    )

    assert outcome.successful_round is not None
    assert outcome.successful_round.number == 1
    assert outcome.successful_round.accepted_attempt.number == 2
    assert outcome.confirm_request is None
    assert len(outcome.attempts) == 2


def test_three_failures_never_create_a_round_or_advance_version() -> None:
    failed = (
        '{"passed":false,"findings":[{"code":"benchmark","message":"mismatch"}],'
        '"required_changes":"use locked benchmark"}'
    )
    reviewer = SubagentReviewer(SequenceLLM([failed, failed, failed]))

    outcome = run_review_gate(
        draft(),
        reviewer,
        lambda prior, report: draft(prior.attempt.number + 1),
        NOW,
    )

    assert MAX_CONSECUTIVE_REVIEW_FAILURES == 3
    assert outcome.successful_round is None
    assert len(outcome.attempts) == 3
    assert {item.spec.id for item in outcome.attempts} == {"s-1", "s-2", "s-3"}
    assert outcome.confirm_request is not None
    assert outcome.confirm_request.kind.value == "review_blocked"
    assert outcome.version_number == 1


def test_restart_with_two_persisted_failures_runs_only_attempt_three() -> None:
    failed = (
        '{"passed":false,"findings":[{"code":"lookahead","message":"future data"}],'
        '"required_changes":"lag inputs"}'
    )
    recorded = []
    outcome = run_review_gate(
        draft(3),
        SubagentReviewer(SequenceLLM([failed])),
        lambda prior, report: draft(prior.attempt.number + 1),
        NOW,
        prior_failures=2,
        on_attempt=recorded.append,
    )
    assert [attempt.number for attempt in recorded] == [3]
    assert outcome.successful_round is None
    assert outcome.confirm_request is not None
```

- [ ] **Step 2: Run the reviewer test and verify RED**

Run: `python -m pytest tests/test_reviewer.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'engine.review'`.

- [ ] **Step 3: Implement the frozen rubric, strict second-LLM adapter, and fail-closed retry gate**

Create `engine/review/__init__.py`:

```python
"""Mandatory independent review gate."""
```

Create `engine/review/subagent.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Callable, Protocol

import httpx

from engine.research.models import (
    Attempt,
    ConfirmKind,
    ConfirmRequest,
    ReviewFinding,
    ReviewReport,
    Round,
    RoundDraft,
)

MAX_CONSECUTIVE_REVIEW_FAILURES = 3

FROZEN_REVIEW_RUBRIC = """You are the mandatory independent reviewer for one alphaloop automatic
research-round draft. Return JSON only with exactly:
{"passed": bool, "findings": [{"code": str, "message": str}], "required_changes": str?}
Fail when any of these is present:
1. lookahead bias: any signal, universe choice, fit, or fill uses information unavailable at decision time;
2. economic-logic drift: thesis_locked, universe, method_set, benchmark, or earning mechanism changed without confirmation;
3. data-snooping: OOS data or repeated trials were used to select parameters without a frozen holdout;
4. benchmark mismatch: the benchmark does not match the locked market and underlying asset class.
Missing evidence is a failure. Do not infer approval from timeout, malformed output, or tool failure."""


class LLMPort(Protocol):
    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


@dataclass(slots=True)
class OpenAICompatibleLLM:
    client: httpx.Client
    base_url: str
    api_key: str
    model: str

    def complete(self, system: str, user: str) -> str:
        response = self.client.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])


class ReviewerPort(Protocol):
    def run(self, round_draft: RoundDraft) -> ReviewReport:
        raise NotImplementedError


@dataclass(slots=True)
class SubagentReviewer:
    llm: LLMPort

    def run(self, round_draft: RoundDraft) -> ReviewReport:
        attempt = round_draft.attempt
        payload = {
            "version_number": round_draft.version_number,
            "round_number": round_draft.round_number,
            "attempt_id": attempt.attempt_id,
            "strategy": {
                "id": attempt.spec.id,
                "thesis_locked": attempt.spec.thesis_locked,
                "universe": repr(attempt.spec.universe),
                "model_family": attempt.spec.model_family,
                "lookback_days": attempt.spec.lookback_days,
            },
            "metrics": repr(attempt.simulation),
            "verification": repr(attempt.verification),
        }
        try:
            raw = self.llm.complete(
                FROZEN_REVIEW_RUBRIC,
                json.dumps(payload, sort_keys=True, default=str),
            )
            parsed = json.loads(raw)
            if set(parsed) - {"passed", "findings", "required_changes"}:
                raise ValueError("unexpected review field")
            if not isinstance(parsed["passed"], bool) or not isinstance(parsed["findings"], list):
                raise ValueError("invalid review field type")
            findings = tuple(
                ReviewFinding(code=item["code"], message=item["message"])
                for item in parsed["findings"]
            )
            required = parsed.get("required_changes")
            if not parsed["passed"] and not required:
                raise ValueError("failed review requires required_changes")
            return ReviewReport(parsed["passed"], findings, required)
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            httpx.HTTPError,
            TimeoutError,
            OSError,
        ) as error:
            return ReviewReport(
                passed=False,
                findings=(ReviewFinding("review_protocol", str(error)),),
                required_changes="retry with a valid independent review result",
            )


RetryFactory = Callable[[RoundDraft, ReviewReport], RoundDraft]
AttemptSink = Callable[[Attempt], None]


@dataclass(frozen=True, slots=True)
class ReviewGateOutcome:
    version_number: int
    attempts: tuple[Attempt, ...]
    successful_round: Round | None
    confirm_request: ConfirmRequest | None


def run_review_gate(
    initial: RoundDraft,
    reviewer: ReviewerPort,
    retry: RetryFactory,
    now: datetime,
    prior_failures: int = 0,
    on_attempt: AttemptSink | None = None,
) -> ReviewGateOutcome:
    if not 0 <= prior_failures < MAX_CONSECUTIVE_REVIEW_FAILURES:
        raise ValueError("prior_failures must be 0, 1, or 2")
    current = initial
    attempts: list[Attempt] = []
    for failure_count in range(
        prior_failures,
        MAX_CONSECUTIVE_REVIEW_FAILURES,
    ):
        report = reviewer.run(current)
        reviewed_attempt = replace(current.attempt, review=report)
        attempts.append(reviewed_attempt)
        if on_attempt is not None:
            on_attempt(reviewed_attempt)
        if report.passed:
            return ReviewGateOutcome(
                version_number=initial.version_number,
                attempts=tuple(attempts),
                successful_round=Round(
                    round_id=f"v{initial.version_number}-r{initial.round_number}",
                    number=initial.round_number,
                    accepted_attempt=reviewed_attempt,
                    completed_at=now,
                ),
                confirm_request=None,
            )
        if failure_count + 1 < MAX_CONSECUTIVE_REVIEW_FAILURES:
            current = retry(replace(current, attempt=reviewed_attempt), report)
            if current.version_number != initial.version_number:
                raise ValueError("automatic review retry cannot advance version")
            if current.attempt.attempt_id in {item.attempt_id for item in attempts}:
                raise ValueError("automatic review retry must be a different attempt")
    return ReviewGateOutcome(
        version_number=initial.version_number,
        attempts=tuple(attempts),
        successful_round=None,
        confirm_request=ConfirmRequest(
            request_id=f"review-blocked-v{initial.version_number}-r{initial.round_number}",
            kind=ConfirmKind.REVIEW_BLOCKED,
            proposed_change="人工检查审查发现，或确认经济逻辑调整后再继续",
            reason="连续3次独立审查未通过",
            effect="研究保持当前版本并停止消耗有效研究时间",
        ),
    )
```

- [ ] **Step 4: Run the reviewer suite and verify GREEN**

Run: `python -m pytest tests/test_reviewer.py -q && python -m mypy engine/review`

Expected: PASS with `5 passed`; mypy exits `0`.

- [ ] **Step 5: Commit the mandatory review gate**

```bash
git add engine/review tests/test_reviewer.py
git commit -m "feat(engine): gate every round on subagent review"
```

### Task 8: Resumable Research Loop, Running-Only Clock, SQLite Heartbeat, and Owner Lock

**Files:**
- Modify: `pyproject.toml`
- Modify: `engine/research/models.py`
- Create: `engine/research/clock.py`
- Create: `engine/research/store.py`
- Create: `engine/research/runtime.py`
- Create: `engine/research/loop.py`
- Test: `tests/test_loop_runtime.py`

**Interfaces:**
- Consumes: `gather(...)`; `specify(...)`; `simulate_daily(...)`; `run_verifiers(...)`; `run_review_gate(...)`; `transition(...)`; `classify_change(...)`
- Produces: `TimeBudget.begin(status: ResearchStatus) -> None`; `TimeBudget.finish(research: Research) -> Research`; `SQLiteStore.create(research: Research) -> None`; `SQLiteStore.load(research_id: str) -> Research`; `SQLiteStore.save(research: Research, expected_updated_at: datetime) -> None`; `SQLiteStore.heartbeat(owner: OwnerRecord, now: datetime) -> None`; `RuntimePaths.default() -> RuntimePaths`; `EngineLock.acquire(paths: RuntimePaths, owner: OwnerKind) -> EngineLock`; `read_live_owner(paths: RuntimePaths) -> OwnerRecord | None`; `ResearchLoop.run_once(research_id: str) -> Research`

The transaction boundary is after an accepted review: incomplete simulations and review-failed attempts may be logged, but `Version.rounds` and `last_completed_round` change in one SQLite transaction only after `ReviewReport.passed` is true. On crash, `load` therefore resumes from the last completed `Round`, never from the middle of `simulate_daily`.

- [ ] **Step 1: Write failing clock, loop, persistence, and lock tests**

Create `tests/test_loop_runtime.py`:

```python
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from engine.metrics import SimulationReport
from engine.research.clock import TimeBudget
from engine.research.loop import ResearchLoop, RoundBuilder
from engine.research.models import (
    AssetClass,
    Attempt,
    ChangeClass,
    ConfirmKind,
    CoverageFloor,
    Market,
    ResearchStatus,
    ReviewReport,
    RoundDraft,
    Slot,
    Universe,
    new_research,
)
from engine.research.runtime import EngineLock, RuntimePaths, read_live_owner
from engine.research.specify import ProposedChange
from engine.research.store import SQLiteStore
from engine.review.subagent import ReviewerPort
from engine.strategy import StrategySpec
from engine.verifiers import VerificationReport, VerifierResult

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


class FakeMonotonic:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


def report(passed: bool = True) -> VerificationReport:
    gate = VerifierResult(
        verifier_id="scorecard.market",
        revision="scorecard-v1",
        passed=passed,
        values={},
        rule="fixture",
    )
    return VerificationReport((gate, gate, gate, gate, gate))


def simulation() -> SimulationReport:
    return SimulationReport(
        r_total=0.2,
        r_ann=0.12,
        sharpe=0.9,
        vol_ann=0.13,
        max_drawdown=-0.2,
        benchmark_id="SPX",
        r_bench_ann=0.08,
        excess_ann=0.04,
        tracking_error=0.06,
        information_ratio=2 / 3,
        sharpe_oos=0.7,
        sharpe_is=1.0,
        oos_segment_returns=(0.02, 0.01, -0.005),
        top_20_crowding_sharpe_impact=0.01,
        annual_turnover=1.0,
        observations=756,
        covered_assets=1,
        missing_pct=0.0,
    )


def strategy(number: int) -> StrategySpec:
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA",))
    return StrategySpec(
        id=f"s-{number}",
        thesis_locked="reversal",
        universe=universe,
        frequency="1d",
        side="long_only",
        method_set=(),
        model_family="mean_reversion",
        lookback_days=20 + number,
        entry_z=1.0,
    )


class FakeBuilder(RoundBuilder):
    def __init__(self) -> None:
        self.calls = 0

    def build(self, research, attempt_number: int) -> RoundDraft:
        self.calls += 1
        attempt = Attempt(
            attempt_id=f"a-{attempt_number}",
            number=attempt_number,
            change_class=ChangeClass.PARAM,
            spec=strategy(attempt_number),
            simulation=simulation(),
            verification=report(),
            review=None,
        )
        return RoundDraft(1, 1, attempt)

    def retry(self, prior: RoundDraft, review: ReviewReport) -> RoundDraft:
        return self.build_for_retry(prior.attempt.number + 1)

    def build_for_retry(self, attempt_number: int) -> RoundDraft:
        return self.build(new_research("ignored", NOW), attempt_number)

    def next_change(self, accepted: Attempt) -> ProposedChange:
        return ProposedChange(
            "lookback_days",
            accepted.spec.lookback_days,
            accepted.spec.lookback_days + 5,
        )


class EconomicBuilder(FakeBuilder):
    def build(self, research, attempt_number: int) -> RoundDraft:
        draft = super().build(research, attempt_number)
        return replace(
            draft,
            attempt=replace(draft.attempt, verification=report(False)),
        )

    def next_change(self, accepted: Attempt) -> ProposedChange:
        return ProposedChange("max_drawdown_floor", -0.25, -0.30)


class PassReviewer(ReviewerPort):
    def run(self, round_draft: RoundDraft) -> ReviewReport:
        return ReviewReport(True, ())


class FailReviewer(ReviewerPort):
    def run(self, round_draft: RoundDraft) -> ReviewReport:
        return ReviewReport(False, (), "choose a different automatic change")


def running_research():
    research = new_research("r-loop", NOW)
    return replace(
        research,
        status=ResearchStatus.RUNNING,
        current_version_number=1,
        versions=(
            __import__("engine.research.models", fromlist=["Version"]).Version(
                "r-loop-v1", 1, research.brief, (), NOW, "confirm_run"
            ),
        ),
    )


def test_time_budget_ticks_only_while_running() -> None:
    monotonic = FakeMonotonic()
    clock = TimeBudget(monotonic)
    running = replace(running_research(), effective_seconds=5.0)
    clock.begin(ResearchStatus.RUNNING)
    monotonic.value = 107.5
    assert clock.finish(running).effective_seconds == 12.5

    paused = replace(running, status=ResearchStatus.PAUSED)
    clock.begin(paused.status)
    monotonic.value = 200.0
    assert clock.finish(paused).effective_seconds == 5.0


def test_passed_review_commits_round_and_completes(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    store.create(running_research())
    loop = ResearchLoop(store, FakeBuilder(), PassReviewer(), TimeBudget(lambda: 10.0), lambda: NOW)

    result = loop.run_once("r-loop")

    assert result.status is ResearchStatus.COMPLETED
    assert len(result.versions[0].rounds) == 1
    assert result.versions[0].rounds[0].accepted_attempt.review.passed
    assert store.last_completed_round("r-loop") == 1


def test_three_review_failures_wait_without_round_or_version_advance(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    store.create(running_research())
    loop = ResearchLoop(store, FakeBuilder(), FailReviewer(), TimeBudget(lambda: 10.0), lambda: NOW)

    result = loop.run_once("r-loop")

    assert result.status is ResearchStatus.AWAITING_CONFIRM
    assert result.pending_confirm is not None
    assert result.pending_confirm.kind is ConfirmKind.REVIEW_BLOCKED
    assert result.current_version_number == 1
    assert result.versions[0].rounds == ()
    assert store.last_completed_round("r-loop") == 0
    assert store.review_failure_count("r-loop", 1, 1) == 3


def test_paused_loop_does_no_work_or_clock_charge(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    paused = replace(running_research(), status=ResearchStatus.PAUSED, effective_seconds=3.0)
    store.create(paused)
    builder = FakeBuilder()
    result = ResearchLoop(
        store,
        builder,
        PassReviewer(),
        TimeBudget(lambda: 99.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert result == paused
    assert builder.calls == 0
    assert result.effective_seconds == 3.0


def test_economic_next_change_waits_and_applies_only_after_approval(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    store.create(running_research())
    loop = ResearchLoop(
        store,
        EconomicBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    )

    waiting = loop.run_once("r-loop")

    assert waiting.status is ResearchStatus.AWAITING_CONFIRM
    assert waiting.current_version_number == 1
    assert waiting.pending_confirm is not None
    assert waiting.pending_confirm.kind is ConfirmKind.ECONOMIC
    assert waiting.pending_confirm.patch == (("max_drawdown_floor", -0.30),)


def test_coverage_below_any_locked_floor_dimension_waits(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    research = running_research()
    research = replace(
        research,
        brief=replace(
            research.brief,
            coverage_floor=Slot(CoverageFloor(2, 10, 0.0), True),
        ),
    )
    store.create(research)
    waiting = ResearchLoop(
        store,
        FakeBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert waiting.status is ResearchStatus.AWAITING_CONFIRM
    assert waiting.pending_confirm is not None
    assert waiting.pending_confirm.kind is ConfirmKind.COVERAGE


def test_sqlite_round_trip_and_heartbeat(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    research = running_research()
    store.create(research)
    assert store.load("r-loop") == research
    paths = RuntimePaths(tmp_path, tmp_path / "engine.lock", tmp_path / "owner.json")
    with EngineLock.acquire(paths, "cli") as lock:
        store.heartbeat(lock.owner, NOW)
        assert read_live_owner(paths) == lock.owner
        assert store.read_heartbeat().owner == "cli"
    assert read_live_owner(paths) is None
```

- [ ] **Step 2: Run the loop/runtime test and verify RED**

Run: `python -m pytest tests/test_loop_runtime.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'engine.research.clock'`.

- [ ] **Step 3: Implement the running clock, lifetime lock, transactional store, and one-round orchestration**

Replace `pyproject.toml` with the complete dependency set:

```toml
[build-system]
requires = ["setuptools>=75", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "alphaloop"
version = "0.2.0"
requires-python = ">=3.12"
dependencies = [
  "akshare",
  "cattrs",
  "httpx",
  "jsonschema",
  "numpy",
  "pandas",
  "platformdirs",
  "portalocker",
  "yfinance",
]

[project.optional-dependencies]
dev = ["build", "mypy", "pandas-stubs", "pyinstaller", "pytest", "ruff"]

[project.scripts]
alphaloop = "apps.cli.main:main"
alphaloop-engine = "engine.main:main"

[tool.setuptools.packages.find]
include = ["engine*", "apps*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
```

Replace `engine/research/models.py` with this complete final domain model:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from engine.metrics import SimulationReport
    from engine.strategy import StrategySpec
    from engine.verifiers import VerificationReport

T = TypeVar("T")


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
class Slot(Generic[T]):
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
    review: ReviewReport | None = None
    data_snapshot_path: Path | None = None
    evidence_paths: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class Round:
    round_id: str
    number: int
    accepted_attempt: Attempt
    completed_at: datetime

    def __post_init__(self) -> None:
        if self.accepted_attempt.review is None or not self.accepted_attempt.review.passed:
            raise ValueError("a successful Round requires a passed review")


@dataclass(frozen=True, slots=True)
class RoundDraft:
    version_number: int
    round_number: int
    attempt: Attempt


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
```

Create `engine/research/clock.py`:

```python
from dataclasses import dataclass, replace
from typing import Callable

from engine.research.models import Research, ResearchStatus


@dataclass(slots=True)
class TimeBudget:
    monotonic: Callable[[], float]
    _started: float | None = None

    def begin(self, status: ResearchStatus) -> None:
        self._started = self.monotonic() if status is ResearchStatus.RUNNING else None

    def finish(self, research: Research) -> Research:
        if self._started is None:
            self._started = None
            return research
        elapsed = max(0.0, self.monotonic() - self._started)
        self._started = None
        return replace(research, effective_seconds=research.effective_seconds + elapsed)
```

Create `engine/research/runtime.py`:

```python
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

import portalocker
from platformdirs import user_runtime_path

OwnerKind = Literal["desktop", "cli"]


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    root: Path
    lock_file: Path
    owner_file: Path

    @classmethod
    def default(cls) -> Self:
        root = Path(user_runtime_path("alphaloop", ensure_exists=True))
        return cls(root, root / "engine.lock", root / "owner.json")


@dataclass(frozen=True, slots=True)
class OwnerRecord:
    owner: OwnerKind
    pid: int
    started_at: str


@dataclass(slots=True)
class EngineLock:
    paths: RuntimePaths
    owner: OwnerRecord
    _handle: object

    @classmethod
    def acquire(cls, paths: RuntimePaths, owner: OwnerKind) -> Self:
        paths.root.mkdir(parents=True, exist_ok=True)
        handle = open(paths.lock_file, "a+", encoding="utf-8")
        try:
            portalocker.lock(handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except portalocker.LockException:
            handle.close()
            raise RuntimeError("alphaloop engine already has an owner")
        record = OwnerRecord(owner, os.getpid(), datetime.now(UTC).isoformat())
        temporary = paths.owner_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(record), sort_keys=True), encoding="utf-8")
        os.replace(temporary, paths.owner_file)
        return cls(paths, record, handle)

    def close(self) -> None:
        if not getattr(self._handle, "closed", True):
            portalocker.unlock(self._handle)
            self._handle.close()
        self.paths.owner_file.unlink(missing_ok=True)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def read_live_owner(paths: RuntimePaths) -> OwnerRecord | None:
    if not paths.owner_file.exists():
        return None
    probe = open(paths.lock_file, "a+", encoding="utf-8")
    try:
        portalocker.lock(probe, portalocker.LOCK_EX | portalocker.LOCK_NB)
    except portalocker.LockException:
        payload = json.loads(paths.owner_file.read_text(encoding="utf-8"))
        return OwnerRecord(**payload)
    else:
        portalocker.unlock(probe)
        paths.owner_file.unlink(missing_ok=True)
        return None
    finally:
        probe.close()
```

Create `engine/research/store.py`:

```python
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cattrs

from engine.research.models import Attempt, Research
from engine.research.runtime import OwnerRecord

CONVERTER = cattrs.Converter()
CONVERTER.register_unstructure_hook(datetime, lambda value: value.isoformat())
CONVERTER.register_structure_hook(datetime, lambda value, _: datetime.fromisoformat(value))
CONVERTER.register_unstructure_hook(Path, str)
CONVERTER.register_structure_hook(Path, lambda value, _: Path(value))

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS researches (
    research_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_completed_round INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS engine_heartbeat (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    owner TEXT NOT NULL,
    pid INTEGER NOT NULL,
    heartbeat_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_attempts (
    attempt_id TEXT PRIMARY KEY,
    research_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    attempt_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class Heartbeat:
    owner: str
    pid: int
    heartbeat_at: datetime


class ConcurrentWrite(RuntimeError):
    """The stored research changed after it was loaded."""


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.executescript(SCHEMA)

    @staticmethod
    def _encode(research: Research) -> str:
        return json.dumps(CONVERTER.unstructure(research), sort_keys=True)

    @staticmethod
    def _decode(payload: str) -> Research:
        return CONVERTER.structure(json.loads(payload), Research)

    def create(self, research: Research) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO researches(research_id,state_json,updated_at) VALUES(?,?,?)",
                (research.research_id, self._encode(research), research.updated_at.isoformat()),
            )

    def load(self, research_id: str) -> Research:
        row = self.connection.execute(
            "SELECT state_json FROM researches WHERE research_id=?",
            (research_id,),
        ).fetchone()
        if row is None:
            raise KeyError(research_id)
        return self._decode(row[0])

    def save(self, research: Research, expected_updated_at: datetime) -> None:
        completed = sum(len(version.rounds) for version in research.versions)
        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE researches
                   SET state_json=?, updated_at=?, last_completed_round=?
                 WHERE research_id=? AND updated_at=?
                """,
                (
                    self._encode(research),
                    research.updated_at.isoformat(),
                    completed,
                    research.research_id,
                    expected_updated_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                raise ConcurrentWrite(research.research_id)

    def last_completed_round(self, research_id: str) -> int:
        row = self.connection.execute(
            "SELECT last_completed_round FROM researches WHERE research_id=?",
            (research_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    def record_review_attempt(
        self,
        research_id: str,
        version_number: int,
        round_number: int,
        attempt: Attempt,
        now: datetime,
    ) -> None:
        if attempt.review is None:
            raise ValueError("review attempt must contain ReviewReport")
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO review_attempts(
                    attempt_id,research_id,version_number,round_number,
                    passed,attempt_json,created_at
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    attempt.attempt_id,
                    research_id,
                    version_number,
                    round_number,
                    int(attempt.review.passed),
                    json.dumps(CONVERTER.unstructure(attempt), sort_keys=True),
                    now.isoformat(),
                ),
            )

    def review_failure_count(
        self,
        research_id: str,
        version_number: int,
        round_number: int,
    ) -> int:
        row = self.connection.execute(
            """
            SELECT COUNT(*) FROM review_attempts
             WHERE research_id=? AND version_number=? AND round_number=? AND passed=0
            """,
            (research_id, version_number, round_number),
        ).fetchone()
        return int(row[0])

    def heartbeat(self, owner: OwnerRecord, now: datetime) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO engine_heartbeat(singleton,owner,pid,heartbeat_at)
                VALUES(1,?,?,?)
                ON CONFLICT(singleton) DO UPDATE SET
                    owner=excluded.owner,pid=excluded.pid,heartbeat_at=excluded.heartbeat_at
                """,
                (owner.owner, owner.pid, now.isoformat()),
            )

    def read_heartbeat(self) -> Heartbeat:
        row = self.connection.execute(
            "SELECT owner,pid,heartbeat_at FROM engine_heartbeat WHERE singleton=1"
        ).fetchone()
        if row is None:
            raise LookupError("heartbeat unavailable")
        return Heartbeat(row[0], int(row[1]), datetime.fromisoformat(row[2]))
```

Create `engine/research/loop.py`:

```python
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Protocol

from engine.research.gather import DataPort, MaterialPort, gather
from engine.research.clock import TimeBudget
from engine.research.models import (
    Attempt,
    ChangeClass,
    ConfirmKind,
    ConfirmRequest,
    CoverageFloor,
    Research,
    ResearchEvent,
    ResearchStatus,
    ReviewReport,
    RoundDraft,
)
from engine.research.simulate import simulate_daily
from engine.research.specify import (
    ModelProposal,
    ProposedChange,
    classify_change,
    specify,
)
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.review.subagent import ReviewerPort, run_review_gate
from engine.strategy import MeanReversionStrategy
from engine.verifiers import run_verifiers


class RoundBuilder(Protocol):
    def build(self, research: Research, attempt_number: int) -> RoundDraft:
        """Run gather → specify → simulate daily → score → all verifiers."""
        raise NotImplementedError

    def retry(self, prior: RoundDraft, review: ReviewReport) -> RoundDraft:
        """Choose a different param/model/research auto-change under the same version."""
        raise NotImplementedError

    def next_change(self, accepted: Attempt) -> ProposedChange:
        """Propose the next change; the loop classifies it before proceeding."""
        raise NotImplementedError


@dataclass(slots=True)
class DefaultRoundBuilder:
    material_ports: tuple[MaterialPort, ...]
    data_port: DataPort
    start: date
    end: date
    snapshot_root: Path

    def build(self, research: Research, attempt_number: int) -> RoundDraft:
        thesis = research.brief.thesis.value
        if thesis is None or research.current_version_number is None:
            raise ValueError("running research requires a locked thesis and version")
        materials = gather(thesis, self.material_ports)
        if not materials:
            raise RuntimeError("no public or local evidence was gathered")
        evidence_root = self.snapshot_root.parent / "materials"
        evidence_root.mkdir(parents=True, exist_ok=True)
        evidence_paths = []
        for material in materials:
            digest = hashlib.sha256(material.material_id.encode("utf-8")).hexdigest()
            path = evidence_root / f"{digest}.json"
            path.write_text(
                json.dumps(asdict(material), sort_keys=True, default=str),
                encoding="utf-8",
            )
            evidence_paths.append(path)
        version = research.versions[research.current_version_number - 1]
        prior = version.rounds[-1].accepted_attempt.spec if version.rounds else None
        lookback = prior.lookback_days + 5 if prior else 20 + 5 * (attempt_number - 1)
        proposal = ModelProposal(
            model_family=prior.model_family if prior else "mean_reversion",
            lookback_days=lookback,
            entry_z=prior.entry_z if prior else 1.0,
            side=prior.side if prior else "long_only",
        )
        spec = specify(research, prior, proposal)
        spec_patch = {
            name: value
            for name, value in version.confirmed_changes
            if name in {"model_family", "lookback_days", "entry_z", "side", "max_drawdown_floor"}
        }
        if spec_patch:
            spec = replace(spec, **spec_patch)
        strategy = MeanReversionStrategy(spec)
        round_number = len(version.rounds) + 1
        snapshot = self.snapshot_root / (
            f"{research.research_id}-v{version.number}-r{round_number}-a{attempt_number}.csv"
        )
        simulation = simulate_daily(
            strategy,
            self.data_port,
            self.start,
            self.end,
            snapshot_path=snapshot,
        )
        verification = run_verifiers(simulation, spec)
        return RoundDraft(
            version_number=version.number,
            round_number=round_number,
            attempt=Attempt(
                attempt_id=f"v{version.number}-r{round_number}-a{attempt_number}",
                number=attempt_number,
                change_class=(
                    ChangeClass.MODEL
                    if prior is None and attempt_number == 1
                    else ChangeClass.PARAM
                ),
                spec=spec,
                simulation=simulation,
                verification=verification,
                data_snapshot_path=snapshot,
                evidence_paths=tuple(evidence_paths),
            ),
        )

    def retry(self, prior: RoundDraft, review: ReviewReport) -> RoundDraft:
        spec = replace(
            prior.attempt.spec,
            id=f"{prior.attempt.spec.id}-retry-{prior.attempt.number + 1}",
            lookback_days=prior.attempt.spec.lookback_days + 5,
        )
        strategy = MeanReversionStrategy(spec)
        snapshot = self.snapshot_root / (
            f"retry-v{prior.version_number}-r{prior.round_number}-a{prior.attempt.number + 1}.csv"
        )
        simulation = simulate_daily(
            strategy,
            self.data_port,
            self.start,
            self.end,
            snapshot_path=snapshot,
        )
        return replace(
            prior,
            attempt=Attempt(
                attempt_id=f"v{prior.version_number}-r{prior.round_number}-a{prior.attempt.number + 1}",
                number=prior.attempt.number + 1,
                change_class=ChangeClass.PARAM,
                spec=spec,
                simulation=simulation,
                verification=run_verifiers(simulation, spec),
                data_snapshot_path=snapshot,
                evidence_paths=prior.attempt.evidence_paths,
            ),
        )

    def next_change(self, accepted: Attempt) -> ProposedChange:
        return ProposedChange(
            field="lookback_days",
            before=accepted.spec.lookback_days,
            after=accepted.spec.lookback_days + 5,
        )


class ResearchLoop:
    def __init__(
        self,
        store: SQLiteStore,
        builder: RoundBuilder,
        reviewer: ReviewerPort,
        budget: TimeBudget,
        now: Callable[[], datetime],
    ) -> None:
        self.store = store
        self.builder = builder
        self.reviewer = reviewer
        self.budget = budget
        self.now = now

    def run_once(self, research_id: str) -> Research:
        research = self.store.load(research_id)
        if research.status is not ResearchStatus.RUNNING:
            return research
        expected_updated_at = research.updated_at
        self.budget.begin(research.status)
        version_number = research.current_version_number
        if version_number is None:
            raise ValueError("running research must have a current version")
        round_number = len(research.versions[version_number - 1].rounds) + 1
        prior_failures = self.store.review_failure_count(
            research.research_id,
            version_number,
            round_number,
        )
        draft = self.builder.build(research, prior_failures + 1)
        outcome = run_review_gate(
            draft,
            self.reviewer,
            self.builder.retry,
            self.now(),
            prior_failures=prior_failures,
            on_attempt=lambda attempt: self.store.record_review_attempt(
                research.research_id,
                version_number,
                round_number,
                attempt,
                self.now(),
            ),
        )
        if outcome.successful_round is None:
            blocked = transition(
                replace(
                    research,
                    consecutive_review_failures=prior_failures + len(outcome.attempts),
                ),
                ResearchEvent.REQUEST_CONFIRM,
                self.now(),
                outcome.confirm_request,
            )
            result = self.budget.finish(blocked)
            self.store.save(result, expected_updated_at)
            return result

        version_index = version_number
        versions = list(research.versions)
        current = versions[version_index - 1]
        versions[version_index - 1] = replace(
            current,
            rounds=current.rounds + (outcome.successful_round,),
        )
        running = replace(
            research,
            versions=tuple(versions),
            consecutive_review_failures=0,
            updated_at=self.now(),
        )
        charged = self.budget.finish(running)
        accepted = outcome.successful_round.accepted_attempt
        floor = charged.brief.coverage_floor.value
        coverage_breached = floor is not None and (
            accepted.simulation.observations < floor.min_years * 252
            or accepted.simulation.covered_assets < floor.min_assets
            or accepted.simulation.missing_pct > floor.max_missing_pct
        )
        if floor is not None and coverage_breached:
            observed_years = max(1, accepted.simulation.observations // 252)
            lowered = CoverageFloor(
                min_assets=accepted.simulation.covered_assets,
                min_years=observed_years,
                max_missing_pct=accepted.simulation.missing_pct,
            )
            request = ConfirmRequest(
                request_id=f"coverage-v{version_number}-r{round_number}",
                kind=ConfirmKind.COVERAGE,
                proposed_change=f"最低历史覆盖从{floor.min_years}年降为{observed_years}年",
                reason="可用日频历史低于已确认的数据覆盖底线",
                effect="确认后开新版本；拒绝则保持底线并寻找其他数据来源",
                change_class=ChangeClass.COVERAGE,
                patch=(("coverage_floor", lowered),),
            )
            result = transition(
                charged,
                ResearchEvent.REQUEST_CONFIRM,
                self.now(),
                request,
            )
        elif accepted.verification.passed:
            result = transition(charged, ResearchEvent.COMPLETE, self.now())
        elif (
            charged.brief.max_effective_hours.value is not None
            and charged.effective_seconds
            >= charged.brief.max_effective_hours.value * 3600
        ):
            result = transition(charged, ResearchEvent.BUDGET_EXHAUSTED, self.now())
        else:
            change = self.builder.next_change(accepted)
            change_class = classify_change(change)
            if change_class in {ChangeClass.ECONOMIC, ChangeClass.COVERAGE}:
                request = ConfirmRequest(
                    request_id=f"change-v{version_number}-r{round_number}",
                    kind=(
                        ConfirmKind.COVERAGE
                        if change_class is ChangeClass.COVERAGE
                        else ConfirmKind.ECONOMIC
                    ),
                    proposed_change=f"{change.field}: {change.before!r} → {change.after!r}",
                    reason="当前冻结验证未全部通过",
                    effect="确认后应用改动并开新版本",
                    change_class=change_class,
                    patch=((change.field, change.after),),
                )
                result = transition(
                    charged,
                    ResearchEvent.REQUEST_CONFIRM,
                    self.now(),
                    request,
                )
            else:
                result = transition(charged, ResearchEvent.AUTO_CONTINUE, self.now())
        self.store.save(result, expected_updated_at)
        return result
```

- [ ] **Step 4: Run runtime tests and the accumulated engine suite**

Run: `python -m pytest tests/test_loop_runtime.py -q && python -m pytest tests -q`

Expected: the runtime file passes with `7 passed`; the accumulated suite passes. Inspect the SQLite row and confirm `last_completed_round` remains `0` after the review-blocked test.

- [ ] **Step 5: Commit resumable runtime ownership**

```bash
git add pyproject.toml engine/research/models.py engine/research/clock.py engine/research/store.py engine/research/runtime.py engine/research/loop.py tests/test_loop_runtime.py
git commit -m "feat(engine): persist resumable owned research loop"
```

### Task 9: Self-Contained Strategy Pack and Disabled Execution Port

**Files:**
- Modify: `engine/strategy.py`
- Create: `engine/execution.py`
- Create: `engine/export.py`
- Create: `contracts/strategy-pack.schema.json`
- Modify: `tests/test_strategy.py`
- Test: `tests/test_export_pack.py`

**Interfaces:**
- Consumes: `Research`, `ResearchStatus`, `AlphaStrategy`, `MarketPanel`, `StrategySpec`, `VerificationReport`, `ReviewReport`
- Produces: `ExecutionPort.submit(self, orders: list[Order]) -> None`; `Broker`; `NotImplementedBroker`; `strategy_pack_eligibility(research: Research) -> ExportEligibility`; `build_strategy_pack(research: Research, strategy: AlphaStrategy, data: MarketPanel, destination: Path) -> Path`

The pack is a frozen artifact, not an order path. Its root contains `run_backtest.py`, `strategy.py`, `execution.py`, `spec.json`, a bundled `data/prices.csv` snapshot, metrics/verifier/reviewer reports, frozen method definitions, material provenance, research history, and schemas. `python run_backtest.py` must work from the extracted directory with no `alphaloop` package installed.

- [ ] **Step 1: Write the failing execution-boundary, eligibility, and isolated-pack tests**

Create `tests/test_export_pack.py`:

```python
import json
import os
import subprocess
import venv
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from engine.execution import NotImplementedBroker, Order
from engine.export import build_strategy_pack, strategy_pack_eligibility
from engine.research.models import (
    AssetClass,
    Attempt,
    ChangeClass,
    Market,
    Reverification,
    ReviewReport,
    Round,
    ResearchStatus,
    Universe,
    Version,
    new_research,
)
from engine.strategy import (
    MarketPanel,
    MeanReversionStrategy,
    StrategySpec,
    run_daily_backtest,
)
from engine.metrics import SimulationDiagnostics, SimulationReport, calculate_metrics
from engine.verifiers import VerificationReport, VerifierResult

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def completed_research():
    base = new_research("r-export", NOW)
    gate = VerifierResult("scorecard.market", "scorecard-v1", True, {}, "fixture pass")
    simulation = accepted_report()
    attempt = Attempt(
        attempt_id="a-export",
        number=1,
        change_class=ChangeClass.MODEL,
        spec=reference_strategy().spec,
        simulation=simulation,
        verification=VerificationReport((gate, gate, gate, gate, gate)),
        review=ReviewReport(True, ()),
    )
    round_ = Round("r-export-v1-r1", 1, attempt, NOW)
    version = Version("r-export-v1", 1, base.brief, (round_,), NOW, "confirm_run")
    return replace(
        base,
        status=ResearchStatus.COMPLETED,
        versions=(version,),
        current_version_number=1,
        export_eligible=True,
        pending_confirm=None,
    )


def reference_strategy() -> MeanReversionStrategy:
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA", "BBB"))
    return MeanReversionStrategy(
        StrategySpec(
            id="mean-reversion-pack",
            thesis_locked="one-day reversal",
            universe=universe,
            frequency="1d",
            side="long_only",
            method_set=(),
            model_family="mean_reversion",
            lookback_days=2,
            entry_z=0.5,
        )
    )


def snapshot() -> MarketPanel:
    prices = pd.DataFrame(
        {"AAA": [10.0, 9.0, 10.0, 11.0], "BBB": [10.0, 11.0, 10.0, 9.0]},
        index=pd.date_range("2026-01-01", periods=4, tz=UTC),
    )
    benchmark = pd.Series(
        [100.0, 100.5, 100.0, 101.0],
        index=prices.index,
        name="SPX",
    )
    return MarketPanel(prices, NOW, benchmark)


def accepted_report() -> SimulationReport:
    strategy = reference_strategy()
    data = snapshot()
    strategy_returns = run_daily_backtest(strategy, data)
    assert data.benchmark_prices is not None
    benchmark_returns = data.benchmark_prices.pct_change(fill_method=None).fillna(0.0)
    return calculate_metrics(
        strategy_returns,
        benchmark_returns,
        "SPX",
        SimulationDiagnostics(
            sharpe_oos=0.7,
            sharpe_is=1.0,
            oos_segment_returns=(0.02, 0.01, -0.005),
            top_20_crowding_sharpe_impact=0.01,
            annual_turnover=1.0,
            covered_assets=2,
            missing_pct=0.0,
        ),
    )


def test_execution_port_is_explicitly_unavailable() -> None:
    broker = NotImplementedBroker()
    with pytest.raises(NotImplementedError, match="outside alphaloop v1"):
        broker.submit([Order("AAA", 1.0)])


def test_export_requires_completed_all_passed_no_pending_and_valid_reverify() -> None:
    research = completed_research()
    assert strategy_pack_eligibility(research).eligible
    assert not strategy_pack_eligibility(
        replace(research, status=ResearchStatus.RUNNING)
    ).eligible
    failed_gate = VerifierResult("overfit.walk", "walk-v1", False, {}, "failed rerun")
    failed_rerun = Reverification(
        round_id="r-export-v1-r1",
        method_id="overfit.walk",
        report=VerificationReport((failed_gate,)),
        passed=False,
        created_at=NOW,
    )
    assert not strategy_pack_eligibility(
        replace(research, reverifications=(failed_rerun,))
    ).eligible


def test_pack_runs_without_alphaloop_installed(tmp_path: Path) -> None:
    archive = build_strategy_pack(
        completed_research(),
        reference_strategy(),
        snapshot(),
        tmp_path / "strategy-pack.zip",
    )
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archive) as pack:
        pack.extractall(extracted)
        names = set(pack.namelist())
    assert {
        "manifest.json",
        "spec.json",
        "strategy.py",
        "execution.py",
        "run_backtest.py",
        "data/prices.csv",
        "data/benchmark.csv",
        "reports/metrics.json",
        "reports/verification.json",
        "reports/review.json",
        "materials/sources.json",
        "history/research.json",
        "schemas/strategy-pack.schema.json",
    } <= names

    environment = tmp_path / "clean-python"
    venv.EnvBuilder(with_pip=False).create(environment)
    isolated_python = (
        environment / "Scripts" / "python.exe"
        if os.name == "nt"
        else environment / "bin" / "python"
    )
    completed = subprocess.run(
        [isolated_python, "run_backtest.py"],
        cwd=extracted,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads((extracted / "results.json").read_text(encoding="utf-8"))
    assert result["strategy_id"] == "mean-reversion-pack"
    assert result["observations"] == 4
    accepted = completed_research().versions[-1].rounds[-1].accepted_attempt.simulation
    for field in (
        "r_total",
        "r_ann",
        "sharpe",
        "vol_ann",
        "max_drawdown",
        "r_bench_ann",
        "excess_ann",
        "tracking_error",
        "information_ratio",
    ):
        assert result[field] == pytest.approx(getattr(accepted, field), abs=1e-12)
    assert "alphaloop" not in (extracted / "run_backtest.py").read_text(encoding="utf-8")


def test_to_executable_uses_the_accepted_research_snapshot() -> None:
    strategy = reference_strategy()
    strategy.data_snapshot = snapshot()
    strategy.accepted_research = completed_research()
    archive = strategy.to_executable()
    assert archive.name == "strategy-pack.zip"
    assert archive.is_file()
```

- [ ] **Step 2: Run the export test and verify RED**

Run: `python -m pytest tests/test_export_pack.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'engine.execution'`.

- [ ] **Step 3: Implement the never-called execution stub and standard-library runnable pack**

Create `engine/execution.py`:

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Order:
    asset: str
    target_weight: float


class ExecutionPort(Protocol):
    def submit(self, orders: list[Order]) -> None:
        raise NotImplementedError


class Broker(ExecutionPort, Protocol):
    """Reserved live-execution seam for another product."""


class NotImplementedBroker:
    def submit(self, orders: list[Order]) -> None:
        raise NotImplementedError("order submission is outside alphaloop v1")
```

Create `engine/export.py`:

```python
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from engine.research.models import Research, ResearchStatus
from engine.strategy import AlphaStrategy, MarketPanel, MeanReversionStrategy
from engine.verifiers import VERIFIER_REVISIONS


@dataclass(frozen=True, slots=True)
class ExportEligibility:
    eligible: bool
    failed_checks: tuple[str, ...]


def strategy_pack_eligibility(research: Research) -> ExportEligibility:
    current_attempt = (
        research.versions[-1].rounds[-1].accepted_attempt
        if research.versions and research.versions[-1].rounds
        else None
    )
    checks = {
        "completed": research.status is ResearchStatus.COMPLETED,
        "all_current_methods_passed": (
            current_attempt is not None and current_attempt.verification.passed
        ),
        "no_pending_confirm": research.pending_confirm is None,
        "all_reverifies_passed": all(
            reverification.passed
            for reverification in research.reverifications
            if current_attempt is not None
            and reverification.round_id
            == research.versions[-1].rounds[-1].round_id
        ),
    }
    return ExportEligibility(
        eligible=all(checks.values()),
        failed_checks=tuple(name for name, passed in checks.items() if not passed),
    )


def _json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=str),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


STRATEGY_MODULE = """import csv
import json
import math
import statistics
from pathlib import Path

TRADING_DAYS = 252


def _returns(values):
    return [0.0] + [
        values[index] / values[index - 1] - 1.0
        for index in range(1, len(values))
    ]


def _annualized(values):
    total = math.prod(1.0 + value for value in values) - 1.0
    return (1.0 + total) ** (TRADING_DAYS / len(values)) - 1.0


def _metrics(strategy, benchmark):
    total = math.prod(1.0 + value for value in strategy) - 1.0
    r_ann = _annualized(strategy)
    r_bench_ann = _annualized(benchmark)
    vol = statistics.stdev(strategy) * math.sqrt(TRADING_DAYS)
    wealth = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in strategy:
        wealth *= 1.0 + value
        peak = max(peak, wealth)
        max_drawdown = min(max_drawdown, wealth / peak - 1.0)
    active = [left - right for left, right in zip(strategy, benchmark)]
    tracking_error = statistics.stdev(active) * math.sqrt(TRADING_DAYS)
    excess = r_ann - r_bench_ann
    return {
        "r_total": total,
        "r_ann": r_ann,
        "sharpe": 0.0 if vol == 0.0 else statistics.mean(strategy) * TRADING_DAYS / vol,
        "vol_ann": vol,
        "max_drawdown": max_drawdown,
        "r_bench_ann": r_bench_ann,
        "excess_ann": excess,
        "tracking_error": tracking_error,
        "information_ratio": 0.0 if tracking_error == 0.0 else excess / tracking_error,
    }


def backtest(root: Path) -> dict:
    spec = json.loads((root / "spec.json").read_text(encoding="utf-8"))
    with (root / "data" / "prices.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with (root / "data" / "benchmark.csv").open(newline="", encoding="utf-8") as handle:
        benchmark_rows = list(csv.DictReader(handle))
    symbols = spec["universe"]["symbols"]
    lookback = int(spec["lookback_days"])
    entry_z = float(spec["entry_z"])
    values = {symbol: [float(row[symbol]) for row in rows] for symbol in symbols}
    asset_returns = {symbol: _returns(series) for symbol, series in values.items()}
    signals = []
    for index in range(len(rows)):
        scores = {}
        for symbol in symbols:
            window = asset_returns[symbol][max(0, index - lookback + 1) : index + 1]
            scores[symbol] = -statistics.mean(window) if len(window) == lookback else 0.0
        dispersion = statistics.stdev(scores.values()) if len(scores) > 1 else 0.0
        center = statistics.mean(scores.values())
        row = {}
        for symbol, score in scores.items():
            zscore = 0.0 if dispersion == 0.0 else (score - center) / dispersion
            row[symbol] = (
                1.0
                if zscore >= entry_z
                else -1.0
                if spec["side"] == "long_short" and zscore <= -entry_z
                else 0.0
            )
        signals.append(row)
    strategy_returns = []
    for index in range(len(rows)):
        prior = signals[index - 1] if index > 0 else {symbol: 0.0 for symbol in symbols}
        gross = sum(abs(value) for value in prior.values()) or 1.0
        strategy_returns.append(
            sum(
                prior[symbol] / gross * asset_returns[symbol][index]
                for symbol in symbols
            )
        )
    benchmark_returns = _returns([float(row["benchmark"]) for row in benchmark_rows])
    return {
        "strategy_id": spec["id"],
        "benchmark_id": spec["benchmark_id"],
        "observations": len(rows),
        **_metrics(strategy_returns, benchmark_returns),
    }
"""

RUNNER = """import json
from pathlib import Path
from strategy import backtest

root = Path(__file__).resolve().parent
result = backtest(root)
(root / "results.json").write_text(
    json.dumps(result, sort_keys=True, indent=2),
    encoding="utf-8",
)
print(json.dumps(result, sort_keys=True))
"""

EXECUTION_STUB = """from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class Order:
    asset: str
    target_weight: float

class ExecutionPort(Protocol):
    def submit(self, orders: list[Order]) -> None:
        raise NotImplementedError

class Broker(ExecutionPort, Protocol):
    \"\"\"Reserved interface; the exported backtest never instantiates it.\"\"\"

class NotImplementedBroker:
    def submit(self, orders: list[Order]) -> None:
        raise NotImplementedError("order submission is outside alphaloop v1")
"""


def build_strategy_pack(
    research: Research,
    strategy: AlphaStrategy,
    data: MarketPanel,
    destination: Path,
) -> Path:
    eligibility = strategy_pack_eligibility(research)
    if not eligibility.eligible:
        raise ValueError(f"research is not strategy-pack eligible: {eligibility.failed_checks}")
    if not isinstance(strategy, MeanReversionStrategy):
        raise TypeError("v1 exporter supports the canonical mean-reversion StrategySpec")
    if not research.versions or not research.versions[-1].rounds:
        raise ValueError("strategy pack requires a completed reviewed round")
    benchmark_prices = data.benchmark_prices
    if benchmark_prices is None:
        raise ValueError("strategy pack requires a frozen benchmark series")
    attempt = research.versions[-1].rounds[-1].accepted_attempt
    if attempt.review is None:
        raise ValueError("strategy pack requires the accepted ReviewReport")
    with TemporaryDirectory(prefix="alphaloop-pack-") as temporary:
        root = Path(temporary)
        spec = asdict(strategy.spec)
        spec["universe"]["market"] = strategy.spec.universe.market.value
        spec["universe"]["asset_class"] = strategy.spec.universe.asset_class.value
        spec["universe"]["underlying_asset_class"] = (
            strategy.spec.universe.underlying_asset_class.value
        )
        spec["method_set"] = [asdict(item) for item in strategy.spec.method_set]
        spec["benchmark_id"] = attempt.simulation.benchmark_id
        _json(root / "spec.json", spec)
        (root / "strategy.py").write_text(STRATEGY_MODULE, encoding="utf-8")
        (root / "run_backtest.py").write_text(RUNNER, encoding="utf-8")
        (root / "execution.py").write_text(EXECUTION_STUB, encoding="utf-8")
        (root / "data").mkdir()
        data.prices.to_csv(root / "data" / "prices.csv", index_label="date")
        benchmark_prices.rename("benchmark").to_csv(
            root / "data" / "benchmark.csv",
            index_label="date",
        )
        _json(root / "reports" / "metrics.json", asdict(attempt.simulation))
        _json(root / "reports" / "verification.json", asdict(attempt.verification))
        _json(root / "reports" / "review.json", asdict(attempt.review))
        _json(root / "methods" / "definitions.json", dict(VERIFIER_REVISIONS))
        sources = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in attempt.evidence_paths
        ]
        _json(root / "materials" / "sources.json", {"sources": sources})
        _json(
            root / "history" / "research.json",
            {
                "research_id": research.research_id,
                "current_version_number": research.current_version_number,
                "round_numbers": [
                    round_.number
                    for version in research.versions
                    for round_ in version.rounds
                ],
                "effective_seconds": research.effective_seconds,
            },
        )
        bundle_root = Path(
            getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
        )
        schema_source = bundle_root / "contracts" / "strategy-pack.schema.json"
        schema_target = root / "schemas" / "strategy-pack.schema.json"
        schema_target.parent.mkdir(parents=True)
        schema_target.write_bytes(schema_source.read_bytes())
        payloads = sorted(path for path in root.rglob("*") if path.is_file())
        _json(
            root / "manifest.json",
            {
                "kind": "strategy_pack",
                "schema_version": "1",
                "tradable_by_alphaloop": False,
                "research_id": research.research_id,
                "strategy_id": strategy.id,
                "files": {
                    path.relative_to(root).as_posix(): _sha256(path)
                    for path in payloads
                },
                "disclaimer": "Research artifact, not investment advice; alphaloop places no orders.",
            },
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())
    return destination
```

Create `contracts/strategy-pack.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://alphaloop.local/contracts/strategy-pack.schema.json",
  "title": "StrategyPackManifest",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "kind",
    "schema_version",
    "tradable_by_alphaloop",
    "research_id",
    "strategy_id",
    "files",
    "disclaimer"
  ],
  "properties": {
    "kind": {"const": "strategy_pack"},
    "schema_version": {"const": "1"},
    "tradable_by_alphaloop": {"const": false},
    "research_id": {"type": "string", "minLength": 1},
    "strategy_id": {"type": "string", "minLength": 1},
    "files": {
      "type": "object",
      "additionalProperties": {"type": "string", "pattern": "^[a-f0-9]{64}$"}
    },
    "disclaimer": {"type": "string", "minLength": 1}
  }
}
```

Finally, replace `MeanReversionStrategy.to_executable` in `engine/strategy.py` with a delegation that uses a caller-supplied snapshot field, keeping the required zero-argument protocol:

```python
@dataclass(slots=True)
class MeanReversionStrategy:
    spec: StrategySpec
    data_snapshot: MarketPanel | None = None
    accepted_research: Research | None = None

    @property
    def id(self) -> str:
        return self.spec.id

    @property
    def thesis(self) -> str:
        return self.spec.thesis_locked

    @property
    def universe(self) -> Universe:
        return self.spec.universe

    @property
    def frequency(self) -> Frequency:
        return self.spec.frequency

    @property
    def side(self) -> Side:
        return self.spec.side

    def generate_signals(self, data: MarketPanel) -> pd.DataFrame:
        returns = data.prices.pct_change(fill_method=None)
        score = -returns.rolling(self.spec.lookback_days).mean()
        dispersion = score.std(axis=1).replace(0.0, np.nan)
        zscore = score.sub(score.mean(axis=1), axis=0).div(dispersion, axis=0)
        signals = pd.DataFrame(0.0, index=data.prices.index, columns=data.prices.columns)
        signals[zscore >= self.spec.entry_z] = 1.0
        if self.spec.side == "long_short":
            signals[zscore <= -self.spec.entry_z] = -1.0
        return signals

    def to_executable(self) -> Path:
        if self.data_snapshot is None or self.accepted_research is None:
            raise ValueError(
                "to_executable requires accepted Research and bundled MarketPanel snapshots"
            )
        from engine.export import build_strategy_pack

        archive = Path(tempfile.mkdtemp(prefix="alphaloop-strategy-")) / "strategy-pack.zip"
        build_strategy_pack(
            self.accepted_research,
            self,
            self.data_snapshot,
            archive,
        )
        return archive
```

Update the typing imports in `engine/strategy.py` exactly as follows:

```python
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from engine.research.models import Research
```

- [ ] **Step 4: Run the isolated pack and full engine suites**

Run: `python -m pytest tests/test_export_pack.py -q && python -m pytest tests -q`

Expected: the export file passes with `4 passed`; the extracted pack command exits `0` in a clean standard-library-only virtual environment, proving it does not import the installed alphaloop package.

- [ ] **Step 5: Commit the independent pack boundary**

```bash
git add engine/execution.py engine/export.py engine/strategy.py contracts/strategy-pack.schema.json tests/test_strategy.py tests/test_export_pack.py
git commit -m "feat(engine): export self-contained strategy packs"
```

### Task 10: Night Desktop Shell and Seven Testable Views

**Files:**
- Create: `apps/desktop/package.json`
- Create: `apps/desktop/package-lock.json`
- Create: `apps/desktop/tsconfig.json`
- Create: `apps/desktop/vite.config.ts`
- Create: `apps/desktop/index.html`
- Create: `apps/desktop/src/main.tsx`
- Create: `apps/desktop/src/contracts.ts`
- Create: `apps/desktop/src/App.tsx`
- Create: `apps/desktop/src/night.css`
- Create: `apps/desktop/src/App.test.tsx`
- Create: `contracts/desktop-api.schema.json`

**Interfaces:**
- Consumes: JSON research status values `draft | running | awaiting_confirm | paused | completed | ended`; `DesktopApi` adapter methods backed by the engine in Task 11
- Produces: `App({api, initialView}: AppProps) -> JSX.Element`; `routeFor(view: DesktopView) -> string`; `ConfirmRunCard`; `AwaitingConfirmCard`; `DesktopApi`; seven `DesktopView` variants `research_list | draft | confirm_run | running | awaiting_confirm | completed | methods`

The visual acceptance reference is [Issue #111](https://github.com/AlphaStrategyAI/alphaloop/issues/111) and its seven linked Figma nodes. Implement the shared 1440×900 shell once; do not fork a shell per screen. `confirm_run` is a draft view, never a seventh research status. Paused and ended research reuse the running/completed workbench as state variants rather than inventing extra Figma screens.

- [ ] **Step 1: Write the failing seven-view and hard-constraint Vitest**

Create `apps/desktop/src/App.test.tsx`:

```tsx
import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App, AwaitingConfirmCard, ConfirmRunCard, routeFor } from "./App";
import type { DesktopApi, DesktopView } from "./contracts";

const api: DesktopApi = {
  fetchView: vi.fn(() => new Promise<DesktopView>(() => undefined)),
  createDraft: vi.fn(async () => "r-new"),
  confirmRun: vi.fn(async () => undefined),
  sendDialogue: vi.fn(async () => undefined),
  pauseResearch: vi.fn(async () => undefined),
  resumeResearch: vi.fn(async () => undefined),
  confirmModification: vi.fn(async () => undefined),
  extendResearch: vi.fn(async () => undefined),
  deleteResearch: vi.fn(async () => undefined),
  resolveConfirm: vi.fn(async () => undefined),
  exportArtifact: vi.fn(async () => undefined),
  reverify: vi.fn(async () => undefined),
  reviseMethod: vi.fn(async () => undefined),
};

const settings = {
  thesis: "美股低波动回归",
  universe: "美股 · 股票",
  max_effective_hours: "12 小时",
  round1_methods: "走样检验 · 样本外稳定 · 拥挤度 · 换手成本",
  coverage_floor: "至少 10 年，缺失不超过 5%",
} as const;

const views: DesktopView[] = [
  {
    kind: "research_list",
    awaiting: {id: "r-wait", title: "美股低波动量价回归", status: "awaiting_confirm"},
    rows: [
      {id: "r-run", title: "中债期限利差交换", status: "running"},
      {id: "r-draft", title: "沪深300波动收缩", status: "draft"},
      {id: "r-pause", title: "美债收益率曲线", status: "paused"},
      {id: "r-done", title: "行业动量", status: "completed"},
      {id: "r-end", title: "转债估值修复", status: "ended"},
    ],
  },
  {kind: "draft", researchId: "r-1", messages: ["我想研究美股低波动回归"], settings},
  {kind: "confirm_run", researchId: "r-1", settings},
  {
    kind: "running",
    researchId: "r-1",
    status: "running",
    version: 2,
    effective: "3h12 / 12h",
    coverage: "覆盖仍在底线之上",
    rounds: ["样本外走样，准备加拥挤度过滤", "量价回归，三项验证"],
  },
  {
    kind: "awaiting_confirm",
    researchId: "r-1",
    version: 2,
    proposed: "信号从量价回归改成回归 + 拥挤度过滤",
    reason: "第 6 轮样本外走样，单纯回归在拥挤月份失效",
    effect: "确认后开出第 3 版；验证方法不变，经济逻辑改变",
  },
  {
    kind: "completed",
    researchId: "r-1",
    status: "completed",
    title: "低波动量价回归 + 拥挤度过滤",
    selectedRoundId: "r-export-v1-r1",
    selectedMethodId: "overfit.walk",
    eligibility: {
      allMethodsPassed: true,
      noPendingConfirm: true,
      reverifiesPassed: true,
    },
  },
  {
    kind: "methods",
    selected: "overfit.walk",
    methods: [
      {id: "overfit.walk", name: "走样检验", revision: "walk-v1", description: "检验策略样本外是否走样。"},
      {id: "stability.oos", name: "样本外稳定", revision: "stability-v1", description: "至少三个样本外区间。"},
    ],
  },
];

describe("Night desktop contract", () => {
  it.each(views)("renders the $kind Figma view in one fixed shell", (view) => {
    render(<App api={api} initialView={view} />);
    expect(screen.getByTestId("night-shell")).toHaveAttribute("data-view", view.kind);
    expect(screen.getByTestId("rail")).toBeInTheDocument();
    expect(screen.getByLabelText("alphaloop")).toBeInTheDocument();
  });

  it("keeps awaiting-confirm as a primary list card before ordinary rows", () => {
    render(<App api={api} initialView={views[0]} />);
    const articles = screen.getAllByRole("article");
    expect(articles[0]).toHaveAttribute("data-kind", "awaiting-primary");
    expect(screen.getAllByTestId("research-row")).toHaveLength(5);
  });

  it("shows exactly five read-only setting slots in draft", () => {
    render(<App api={api} initialView={views[1]} />);
    expect(screen.getAllByTestId("brief-slot")).toHaveLength(5);
    expect(screen.getByPlaceholderText("把方向说清楚，不用填表。")).toBeInTheDocument();
  });

  it("uses two distinct non-modal confirmation cards", () => {
    const {rerender} = render(<ConfirmRunCard api={api} view={views[2] as Extract<DesktopView, {kind: "confirm_run"}>} />);
    expect(screen.getByTestId("confirm-run-card")).not.toHaveAttribute("role", "dialog");
    rerender(<AwaitingConfirmCard api={api} view={views[4] as Extract<DesktopView, {kind: "awaiting_confirm"}>} />);
    expect(screen.getByTestId("awaiting-confirm-card")).not.toHaveAttribute("role", "dialog");
    expect(screen.queryByTestId("confirm-run-card")).not.toBeInTheDocument();
  });

  it("offers all three awaiting-confirm decisions without a default", () => {
    render(<App api={api} initialView={views[4]} />);
    fireEvent.click(screen.getByRole("button", {name: "同意，开新的一版"}));
    fireEvent.click(screen.getByRole("button", {name: "不同意，维持原逻辑继续"}));
    fireEvent.click(screen.getByRole("button", {name: "暂停，我自己改"}));
    expect(api.resolveConfirm).toHaveBeenNthCalledWith(1, "r-1", "approve_new_version");
    expect(api.resolveConfirm).toHaveBeenNthCalledWith(2, "r-1", "reject_keep_logic");
    expect(api.resolveConfirm).toHaveBeenNthCalledWith(3, "r-1", "pause_and_edit");
  });

  it("has no order or account action on any screen", () => {
    for (const view of views) {
      const rendered = render(<App api={api} initialView={view} />);
      const actions = screen.queryAllByRole("button").map((button) => button.textContent ?? "").join(" ");
      expect(actions).not.toMatch(/下单|买入|卖出|连接账户|开始交易/);
      rendered.unmount();
    }
  });

  it("routes every research state through one research route", () => {
    expect(routeFor(views[1])).toBe("#/research/r-1");
    expect(routeFor(views[2])).toBe("#/research/r-1");
    expect(routeFor(views[3])).toBe("#/research/r-1");
    expect(routeFor(views[4])).toBe("#/research/r-1");
    expect(routeFor(views[5])).toBe("#/research/r-1");
    expect(routeFor(views[0])).toBe("#/research");
    expect(routeFor(views[6])).toBe("#/methods/overfit.walk");
  });
});
```

- [ ] **Step 2: Run the desktop test and verify RED**

Run: `npm --prefix apps/desktop test`

Expected: FAIL because `apps/desktop/package.json` and the React application do not exist.

- [ ] **Step 3: Create the React/Vite app, desktop contract, seven views, and locked Night CSS**

Create `apps/desktop/package.json`:

```json
{
  "name": "@alphaloop/desktop",
  "private": true,
  "version": "0.2.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "test": "vitest run",
    "typecheck": "tsc --noEmit",
    "build": "tsc --noEmit && vite build",
    "tauri": "tauri"
  }
}
```

Install current releases and generate `package-lock.json`:

```bash
npm --prefix apps/desktop install react@latest react-dom@latest @tauri-apps/api@latest
npm --prefix apps/desktop install --save-dev @tauri-apps/cli@latest @testing-library/jest-dom@latest @testing-library/react@latest @types/react@latest @types/react-dom@latest @vitejs/plugin-react@latest jsdom@latest typescript@latest vite@latest vitest@latest
npm --prefix apps/desktop install @fontsource/noto-serif@latest @fontsource/noto-serif-sc@latest @fontsource/noto-sans-sc@latest @fontsource/ibm-plex-mono@latest
```

Create `apps/desktop/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": []
}
```

Create `apps/desktop/vite.config.ts`:

```ts
import {defineConfig} from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {port: 1420, strictPort: true},
  envPrefix: ["VITE_", "TAURI_"],
  test: {environment: "jsdom"},
});
```

Create `apps/desktop/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>alphaloop</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `apps/desktop/src/contracts.ts`:

```ts
export type ResearchStatus =
  | "draft"
  | "running"
  | "awaiting_confirm"
  | "paused"
  | "completed"
  | "ended";

export type ConfirmationDecision =
  | "approve_new_version"
  | "reject_keep_logic"
  | "pause_and_edit";

export type ExportKind = "strategy_pack" | "research_record";

export interface BriefSettings {
  thesis: string;
  universe: string;
  max_effective_hours: string;
  round1_methods: string;
  coverage_floor: string;
}

export interface ResearchSummary {
  id: string;
  title: string;
  status: ResearchStatus;
}

export interface ValidationMethod {
  id: string;
  name: string;
  revision: string;
  description: string;
}

export type DesktopView =
  | {kind: "research_list"; awaiting?: ResearchSummary; rows: readonly ResearchSummary[]}
  | {kind: "draft"; researchId: string; messages: readonly string[]; settings: BriefSettings}
  | {kind: "confirm_run"; researchId: string; settings: BriefSettings}
  | {
      kind: "running";
      researchId: string;
      status: "running" | "paused";
      version: number;
      effective: string;
      coverage: string;
      rounds: readonly string[];
    }
  | {
      kind: "awaiting_confirm";
      researchId: string;
      version: number;
      proposed: string;
      reason: string;
      effect: string;
    }
  | {
      kind: "completed";
      researchId: string;
      status: "completed" | "ended";
      title: string;
      selectedRoundId: string;
      selectedMethodId: string;
      eligibility: {
        allMethodsPassed: boolean;
        noPendingConfirm: boolean;
        reverifiesPassed: boolean;
      };
    }
  | {kind: "methods"; selected?: string; methods: readonly ValidationMethod[]};

export interface DesktopApi {
  fetchView(route: string): Promise<DesktopView>;
  createDraft(): Promise<string>;
  confirmRun(researchId: string): Promise<void>;
  sendDialogue(researchId: string, message: string): Promise<void>;
  pauseResearch(researchId: string): Promise<void>;
  resumeResearch(researchId: string): Promise<void>;
  confirmModification(researchId: string): Promise<void>;
  extendResearch(researchId: string, hours: number): Promise<void>;
  deleteResearch(researchId: string): Promise<void>;
  resolveConfirm(researchId: string, decision: ConfirmationDecision): Promise<void>;
  exportArtifact(researchId: string, kind: ExportKind): Promise<void>;
  reverify(researchId: string, roundId: string, methodId: string): Promise<void>;
  reviseMethod(methodId: string, definition: string): Promise<void>;
}
```

Create `apps/desktop/src/App.tsx`:

```tsx
import {FormEvent, useEffect, useState} from "react";

import type {
  DesktopApi,
  DesktopView,
  ResearchStatus,
  ValidationMethod,
} from "./contracts";
import "./night.css";

export interface AppProps {
  api: DesktopApi;
  initialView: DesktopView;
}

const statusLabels: Record<ResearchStatus, string> = {
  draft: "草稿",
  running: "运行中",
  awaiting_confirm: "等待确认",
  paused: "已暂停",
  completed: "已完成",
  ended: "已结束（未通过）",
};

export function routeFor(view: DesktopView): string {
  if (view.kind === "research_list") return "#/research";
  if (view.kind === "methods") return `#/methods${view.selected ? `/${view.selected}` : ""}`;
  return `#/research/${view.researchId}`;
}

function Logo() {
  return <div className="logo" aria-label="alphaloop">α<span /></div>;
}

function NightShell({view, children}: {view: DesktopView; children: React.ReactNode}) {
  const methods = view.kind === "methods";
  const hostStatus =
    view.kind === "awaiting_confirm" ? "等待确认" :
    view.kind === "running" ? "运行中" :
    view.kind === "completed" ? "已完成" : "本机静";
  return (
    <main className="night-shell" data-testid="night-shell" data-view={view.kind}>
      <aside className="rail" data-testid="rail">
        <div className="rail-center">
          <Logo />
          <nav aria-label="主导航">
            <a className={!methods ? "active" : ""} href="#/research">研究</a>
            <a className={methods ? "active" : ""} href="#/methods">方法库</a>
          </nav>
        </div>
        <div className={`host-status ${view.kind}`}>● {hostStatus}</div>
      </aside>
      <section className={`content ${view.kind}`}>{children}</section>
    </main>
  );
}

function StatusPill({status}: {status: ResearchStatus}) {
  return <span className={`status-pill ${status}`}>{statusLabels[status]}</span>;
}

function ResearchList({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "research_list"}>}) {
  return (
    <div className="browse list-screen">
      <header className="list-header">
        <p>一条对话，一次研究。等你确认的会排在最上面。</p>
        <button className="quiet-button" onClick={() => void api.createDraft()}>新建研究</button>
      </header>
      {view.awaiting && (
        <article className="awaiting-primary" data-kind="awaiting-primary">
          <StatusPill status="awaiting_confirm" />
          <h2>{view.awaiting.title}</h2>
          <p>美股 · 股票 · 等了 2 小时</p>
        </article>
      )}
      <div className="research-rows">
        {view.rows.map((row) => (
          <article className="research-row" data-testid="research-row" key={row.id}>
            <div><h3>{row.title}</h3><p>最近活动保留在本机</p></div>
            <div className="row-actions">
              <a href={`#/research/${row.id}`}>进入</a>
              <button onClick={() => {
                const accepted = window.confirm(
                  "删除会永久移除对话、版本、迭代与验证记录及导出资格；已导出的本机文件不受影响。",
                );
                if (accepted) void api.deleteResearch(row.id);
              }}>删除</button>
              <StatusPill status={row.status} />
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

const settingLabels = [
  ["thesis", "大致原理"],
  ["universe", "资产类别"],
  ["max_effective_hours", "最长研究时间"],
  ["round1_methods", "第一轮验证方法"],
  ["coverage_floor", "最低数据覆盖"],
] as const;

function Settings({values}: {values: Extract<DesktopView, {kind: "draft" | "confirm_run"}>["settings"]}) {
  return (
    <aside className="settings">
      <p className="eyebrow">研究设定</p>
      {settingLabels.map(([key, label]) => (
        <div data-testid="brief-slot" key={key}>
          <dt>{label}</dt>
          <dd>{values[key] || "未锁定"}</dd>
        </div>
      ))}
    </aside>
  );
}

function DraftScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "draft"}>}) {
  const [message, setMessage] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (message.trim()) void api.sendDialogue(view.researchId, message.trim());
  };
  return (
    <div className="draft-layout">
      <section className="conversation">
        <h1>新研究</h1>
        {view.messages.map((item) => <p className="message" key={item}>{item}</p>)}
        <p className="message system">我会逐项锁定原理、资产、时间、方法和覆盖底线。</p>
        <form onSubmit={submit}>
          <input value={message} onChange={(event) => setMessage(event.target.value)} placeholder="把方向说清楚，不用填表。" />
        </form>
      </section>
      <Settings values={view.settings} />
    </div>
  );
}

export function ConfirmRunCard({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "confirm_run"}>}) {
  return (
    <article className="confirm-card" data-testid="confirm-run-card">
      <h1>确认开跑</h1>
      <p>认下这次研究做什么、跑多久、拿什么验证。确认前不会自己开始。</p>
      <Settings values={view.settings} />
      <div className="actions">
        <button className="cyan-button" onClick={() => void api.confirmRun(view.researchId)}>确认开跑</button>
        <a href={`#/research/${view.researchId}`}>再改改</a>
      </div>
    </article>
  );
}

function RunningScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "running"}>}) {
  const [modification, setModification] = useState("");
  return (
    <div className="focus running-screen">
      <header><StatusPill status={view.status} /> 第 {view.version} 版 · 有效研究 {view.effective} · {view.coverage}</header>
      <h1>迭代与验证</h1>
      {view.rounds.map((round, index) => (
        <article className="round-card" key={round}>
          <small>v{view.version} · 第 {view.rounds.length - index} 轮</small>
          <h2>{round}</h2>
          <p>每轮都显示市场基准指标、四项验证和独立审查。</p>
        </article>
      ))}
      {view.status === "running" ? (
        <button className="quiet-button" onClick={() => void api.pauseResearch(view.researchId)}>暂停</button>
      ) : (
        <>
          <button className="quiet-button" onClick={() => void api.resumeResearch(view.researchId)}>按当前版本继续</button>
          <input value={modification} onChange={(event) => setModification(event.target.value)} placeholder="说明要改的研究设定" />
          <button className="quiet-button" disabled={!modification.trim()} onClick={() => void (async () => {
            await api.sendDialogue(view.researchId, modification.trim());
            await api.confirmModification(view.researchId);
          })()}>确认修改并开新版</button>
        </>
      )}
    </div>
  );
}

export function AwaitingConfirmCard({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "awaiting_confirm"}>}) {
  return (
    <article className="awaiting-card" data-testid="awaiting-confirm-card">
      <p className="eyebrow">等待确认 · 第 {view.version} 版 · 这段时间不计入额度</p>
      <h1>经济逻辑要改了</h1>
      <section><small>现在打算改什么</small><p>{view.proposed}</p></section>
      <section><small>为什么要改</small><p>{view.reason}</p></section>
      <section><small>改了之后会变成什么样</small><p>{view.effect}</p></section>
      <div className="decision-stack">
        <button className="cyan-button" onClick={() => void api.resolveConfirm(view.researchId, "approve_new_version")}>同意，开新的一版</button>
        <button onClick={() => void api.resolveConfirm(view.researchId, "reject_keep_logic")}>不同意，维持原逻辑继续</button>
        <button onClick={() => void api.resolveConfirm(view.researchId, "pause_and_edit")}>暂停，我自己改</button>
      </div>
    </article>
  );
}

function CompletedScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "completed"}>}) {
  const [extensionHours, setExtensionHours] = useState("4");
  const [modification, setModification] = useState("");
  const checks = [
    ["当前验证方法全部通过", view.eligibility.allMethodsPassed],
    ["没有待确认", view.eligibility.noPendingConfirm],
    ["重验仍然成立", view.eligibility.reverifiesPassed],
  ] as const;
  const eligible = checks.every(([, passed]) => passed);
  return (
    <div className="focus completed-screen">
      <StatusPill status={view.status} />
      <p>alphaloop 到这里结束，不提供执行入口。</p>
      <div className="eligibility">{checks.map(([label, passed]) => <span key={label}>{passed ? "●" : "○"} {label}</span>)}</div>
      <article className="result-card">
        <h1>{view.title}</h1>
        <p>美股 · 股票 · 经过市场基准和全部额外验证</p>
        <button disabled={!eligible || view.status === "ended"} onClick={() => void api.exportArtifact(view.researchId, "strategy_pack")}>导出策略包</button>
        <button className="text-button" onClick={() => void api.reverify(view.researchId, view.selectedRoundId, view.selectedMethodId)}>对某一步重新验证</button>
        <button className="text-button" onClick={() => void api.exportArtifact(view.researchId, "research_record")}>导出研究记录包</button>
        <label>
          改策略再跑
          <input value={modification} onChange={(event) => setModification(event.target.value)} placeholder="说明要改的研究设定" />
          <button disabled={!modification.trim()} onClick={() => void (async () => {
            await api.sendDialogue(view.researchId, modification.trim());
            await api.confirmModification(view.researchId);
          })()}>确认修改并开新版</button>
        </label>
        {view.status === "ended" && (
          <label>
            延长有效研究小时
            <input value={extensionHours} onChange={(event) => setExtensionHours(event.target.value)} inputMode="decimal" />
            <button onClick={() => void api.extendResearch(view.researchId, Number(extensionHours))}>确认延长并开新版</button>
          </label>
        )}
      </article>
    </div>
  );
}

function MethodDetail({api, method}: {api: DesktopApi; method: ValidationMethod}) {
  return (
    <section className="method-detail">
      <h1>{method.name}</h1>
      <p>{method.description}</p>
      <p>当前冻结定义：{method.revision}</p>
      <button className="quiet-button" onClick={() => void api.reviseMethod(method.id, method.description)}>编辑为新定义</button>
      <p>旧研究和已导出的策略包仍引用原定义。</p>
    </section>
  );
}

function MethodsScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "methods"}>}) {
  const selected = view.methods.find((item) => item.id === view.selected) ?? view.methods[0];
  return (
    <div className="methods-layout">
      <aside className="method-list">
        <p>编辑得到新定义，旧研究不改写。</p>
        {view.methods.map((method) => <a href={`#/methods/${method.id}`} key={method.id}>{method.name}<small>{method.revision}</small></a>)}
      </aside>
      {selected && <MethodDetail api={api} method={selected} />}
    </div>
  );
}

function Screen({api, initialView: view}: AppProps) {
  switch (view.kind) {
    case "research_list": return <ResearchList api={api} view={view} />;
    case "draft": return <DraftScreen api={api} view={view} />;
    case "confirm_run": return <div className="focus"><ConfirmRunCard api={api} view={view} /></div>;
    case "running": return <RunningScreen api={api} view={view} />;
    case "awaiting_confirm": return <div className="focus"><AwaitingConfirmCard api={api} view={view} /></div>;
    case "completed": return <CompletedScreen api={api} view={view} />;
    case "methods": return <MethodsScreen api={api} view={view} />;
  }
}

export function App({api, initialView}: AppProps) {
  const [view, setView] = useState(initialView);
  useEffect(() => {
    let active = true;
    const refresh = () => {
      void api.fetchView(routeFor(view)).then((next) => {
        if (active) setView(next);
      });
    };
    const timer = window.setInterval(refresh, 1_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [api, view]);
  return <NightShell view={view}><Screen api={api} initialView={view} /></NightShell>;
}
```

Create `apps/desktop/src/night.css`:

```css
:root {
  color-scheme: dark;
  --void: #07090C;
  --glass: #12161C;
  --ink: #E8EEF5;
  --mute: #8B97A8;
  --line: #1E2530;
  --cyan: #5EEAD4;
  --run: #60A5FA;
  --ok: #34D399;
  --stop: #F87171;
  --hold: #FBBF24;
  --radius-card: 16px;
  --radius-control: 10px;
  font-family: "Noto Sans SC", sans-serif;
  background: var(--void);
  color: var(--ink);
}

* { box-sizing: border-box; }
body { margin: 0; background: var(--void); }
button, input { font: inherit; }
button, a { transition: transform 320ms ease-out, opacity 320ms ease-out, border-color 320ms ease-out; }
button:active { transform: scale(.98); }

.night-shell {
  width: 1440px;
  min-height: 900px;
  display: grid;
  grid-template-columns: 148px 1fr;
  overflow: hidden;
  background: var(--void);
}
.rail {
  position: relative;
  width: 148px;
  min-height: 900px;
  border-right: 1px solid var(--line);
  background: var(--void);
}
.rail-center { position: absolute; top: 50%; transform: translateY(-50%); }
.logo {
  width: 148px;
  height: 148px;
  display: grid;
  place-items: center;
  position: relative;
  font: 500 88px/1 "Noto Serif", serif;
}
.logo span { position: absolute; width: 18px; height: 18px; border-radius: 50%; background: var(--ink); top: 47px; right: 47px; }
nav { display: grid; gap: 4px; padding: 0 20px; font: 17px "Noto Serif SC", serif; }
nav a { color: var(--mute); text-decoration: none; padding: 11px 12px; border: 1px solid transparent; border-radius: var(--radius-control); }
nav a.active { color: var(--ink); background: var(--glass); border-color: var(--line); box-shadow: 0 8px 24px rgba(0, 0, 0, .3); }
.host-status { position: absolute; left: 20px; bottom: 28px; color: var(--mute); font-size: 12px; }
.host-status.running { color: var(--run); }
.host-status.completed { color: var(--ok); }
.host-status.awaiting_confirm { color: var(--cyan); }
.content { min-width: 0; min-height: 900px; }
.content.confirm_run, .content.awaiting_confirm {
  background: radial-gradient(ellipse at 50% 38%, rgba(94, 234, 212, .12), transparent 28%);
}
.browse { padding: 56px 72px; }
.focus { width: 720px; margin: 0 auto; padding-top: 210px; }
h1, h2, h3 { font-family: "Noto Serif SC", serif; font-weight: 500; }
h1 { font-size: 36px; }
p, small { color: var(--mute); }
button { color: var(--ink); background: var(--glass); border: 1px solid var(--line); border-radius: var(--radius-control); padding: 11px 18px; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: .45; }
.quiet-button:hover { border-color: var(--mute); }
.list-header { display: flex; justify-content: space-between; align-items: center; }
.awaiting-primary {
  margin: 36px 0 52px;
  padding: 28px 32px;
  background: var(--glass);
  border: 1px solid var(--cyan);
  border-radius: var(--radius-card);
  box-shadow: 0 0 38px rgba(94, 234, 212, .22);
  animation: waiting-breath 2.4s ease-in-out infinite;
}
@keyframes waiting-breath { 50% { opacity: .88; transform: scale(.998); } }
.research-row { display: flex; align-items: center; justify-content: space-between; min-height: 74px; }
.research-row h3, .research-row p { margin: 4px 0; }
.row-actions { display: flex; align-items: center; gap: 12px; }
.row-actions a { color: var(--mute); }
.status-pill { padding: 5px 9px; border-radius: var(--radius-control); background: var(--glass); font-size: 12px; }
.status-pill.running { color: var(--run); }
.status-pill.completed { color: var(--ok); }
.status-pill.ended { color: var(--stop); }
.status-pill.paused { color: var(--hold); }
.status-pill.draft { color: var(--mute); }
.status-pill.awaiting_confirm { color: var(--cyan); }
.draft-layout { min-height: 900px; display: grid; grid-template-columns: 1fr 240px; gap: 48px; padding-left: 64px; }
.conversation { position: relative; padding-top: 46px; }
.message { max-width: 640px; background: var(--glass); border: 1px solid var(--line); border-radius: var(--radius-control); padding: 14px 18px; }
.conversation form { position: absolute; bottom: 40px; width: 640px; }
.conversation input { width: 100%; color: var(--ink); background: var(--glass); border: 1px solid var(--line); border-radius: var(--radius-control); padding: 16px; }
.settings { background: var(--glass); border: 1px solid var(--line); padding: 36px 24px; }
.settings div { margin: 20px 0; }
.settings dt, .eyebrow { color: var(--mute); font-size: 12px; }
.settings dd { margin: 6px 0 0; }
.confirm-card, .awaiting-card {
  border: 1px solid var(--cyan);
  border-radius: var(--radius-card);
  padding: 28px 32px;
  background: linear-gradient(120deg, rgba(94, 234, 212, .18), var(--glass) 55%);
  box-shadow: 0 0 42px rgba(94, 234, 212, .18);
}
.confirm-card .settings { padding: 8px 0; background: transparent; border: 0; }
.confirm-card .settings div { display: flex; justify-content: space-between; margin: 13px 0; }
.cyan-button { background: var(--cyan); border-color: var(--cyan); color: var(--void); font-weight: 700; }
.actions { display: grid; grid-template-columns: 1fr auto; gap: 16px; align-items: center; }
.actions a { color: var(--mute); }
.running-screen { padding-top: 205px; }
.running-screen header { color: var(--mute); font: 13px "IBM Plex Mono", monospace; }
.round-card, .result-card { margin: 12px 0; padding: 20px 24px; background: var(--glass); border: 1px solid var(--line); border-radius: var(--radius-card); }
.round-card h2 { font-size: 17px; }
.awaiting-card { width: 640px; }
.awaiting-card section { margin: 20px 0; }
.awaiting-card section p { color: var(--ink); }
.decision-stack { display: grid; gap: 8px; }
.completed-screen { width: 640px; text-align: center; }
.eligibility { display: flex; justify-content: center; gap: 12px; color: var(--ok); font-size: 12px; }
.result-card { margin-top: 28px; text-align: left; }
.result-card button { margin-right: 10px; }
.text-button { border: 0; background: transparent; color: var(--mute); }
.methods-layout { display: grid; grid-template-columns: 260px 1fr; min-height: 900px; }
.method-list { padding: 52px 28px; border-right: 1px solid var(--line); }
.method-list a { display: grid; color: var(--ink); text-decoration: none; padding: 14px; border-radius: var(--radius-control); }
.method-list a:first-of-type { background: var(--glass); border: 1px solid var(--line); }
.method-list small { margin-top: 4px; }
.method-detail { padding: 52px 64px; background: var(--glass); }
```

Create `apps/desktop/src/main.tsx` with local fonts and an explicit preview adapter; Task 11 replaces the preview adapter with Tauri invokes:

```tsx
import "@fontsource/noto-serif/500.css";
import "@fontsource/noto-serif-sc/500.css";
import "@fontsource/noto-sans-sc/400.css";
import "@fontsource/ibm-plex-mono/400.css";
import {StrictMode} from "react";
import {createRoot} from "react-dom/client";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

const previewApi: DesktopApi = {
  async fetchView() { return preview; },
  async createDraft() { return "preview-draft"; },
  async confirmRun() { return undefined; },
  async sendDialogue() { return undefined; },
  async pauseResearch() { return undefined; },
  async resumeResearch() { return undefined; },
  async confirmModification() { return undefined; },
  async extendResearch() { return undefined; },
  async deleteResearch() { return undefined; },
  async resolveConfirm() { return undefined; },
  async exportArtifact() { return undefined; },
  async reverify() { return undefined; },
  async reviseMethod() { return undefined; },
};

const preview: DesktopView = {kind: "research_list", rows: []};
createRoot(document.getElementById("root")!).render(
  <StrictMode><App api={previewApi} initialView={preview} /></StrictMode>,
);
```

Create `contracts/desktop-api.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://alphaloop.local/contracts/desktop-api.schema.json",
  "title": "DesktopRequest",
  "oneOf": [
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "route"],
      "properties": {
        "type": {"const": "fetch_view"},
        "route": {"type": "string", "pattern": "^#/(research|methods)"}
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type"],
      "properties": {"type": {"const": "create_draft"}}
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "research_id"],
      "properties": {
        "type": {
          "enum": [
            "confirm_run",
            "pause",
            "resume",
            "confirm_modification",
            "delete_research"
          ]
        },
        "research_id": {"type": "string", "minLength": 1}
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "research_id", "decision"],
      "properties": {
        "type": {"const": "resolve_confirm"},
        "research_id": {"type": "string", "minLength": 1},
        "decision": {
          "enum": ["approve_new_version", "reject_keep_logic", "pause_and_edit"]
        }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "research_id", "hours"],
      "properties": {
        "type": {"const": "extend_research"},
        "research_id": {"type": "string", "minLength": 1},
        "hours": {"type": "number", "exclusiveMinimum": 0, "maximum": 720}
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "research_id", "round_id", "method_id"],
      "properties": {
        "type": {"const": "reverify"},
        "research_id": {"type": "string", "minLength": 1},
        "round_id": {"type": "string", "minLength": 1},
        "method_id": {"type": "string", "minLength": 1}
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "research_id", "message"],
      "properties": {
        "type": {"const": "send_dialogue"},
        "research_id": {"type": "string", "minLength": 1},
        "message": {"type": "string", "minLength": 1}
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "research_id", "kind"],
      "properties": {
        "type": {"const": "export_artifact"},
        "research_id": {"type": "string", "minLength": 1},
        "kind": {"enum": ["strategy_pack", "research_record"]}
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "method_id", "definition"],
      "properties": {
        "type": {"const": "revise_method"},
        "method_id": {"type": "string", "minLength": 1},
        "definition": {"type": "string", "minLength": 1}
      }
    }
  ]
}
```

- [ ] **Step 4: Run UI tests, type checking, and the production web build**

Run: `npm --prefix apps/desktop test && npm --prefix apps/desktop run typecheck && npm --prefix apps/desktop run build`

Expected: Vitest PASS with `13 tests` (`7` parameterized view cases plus `6` hard-constraint cases), TypeScript exits `0`, and Vite writes `apps/desktop/dist/index.html`. At 1440×900, compare each rendered route to the corresponding #111 Figma node and confirm Rail/Logo dimensions, focused-column widths, typography, card hierarchy, and cyan scope.

- [ ] **Step 5: Commit the seven-screen Night UI**

```bash
git add apps/desktop contracts/desktop-api.schema.json
git commit -m "feat(desktop): add Night seven-screen shell"
```

### Task 11: Tauri-Owned Sidecar Lifecycle and Native macOS/Windows/Linux Bundles

**Files:**
- Create: `apps/desktop/src-tauri/Cargo.toml`
- Create: `apps/desktop/src-tauri/build.rs`
- Create: `apps/desktop/src-tauri/tauri.conf.json`
- Create: `apps/desktop/src-tauri/capabilities/default.json`
- Create: `apps/desktop/src-tauri/src/main.rs`
- Create: `apps/desktop/src-tauri/src/lib.rs`
- Create: `apps/desktop/src-tauri/src/commands.rs`
- Create: `apps/desktop/src-tauri/src/sidecar.rs`
- Test: `apps/desktop/src-tauri/tests/sidecar_lifecycle.rs`
- Create: `packaging/alphaloop-engine.spec`
- Create: `scripts/stage_sidecar.py`
- Modify: `apps/desktop/src/main.tsx`

**Interfaces:**
- Consumes: `alphaloop-engine --owner desktop`; JSON first-line handshake `{"protocol_version":1,"status":"ready"|"already_running","owner":"desktop"|"cli","pid":int,"endpoint":str,"auth_token":str}`; `DesktopApi`
- Produces: `EngineSupervisor.adopt_owned(child: Box<dyn ManagedChild>, owner: OwnerRecord) -> Result<(), SidecarError>`; `EngineSupervisor.attach(owner: OwnerRecord) -> Result<(), SidecarError>`; `EngineSupervisor.close_last_window() -> Result<bool, SidecarError>`; `EngineSupervisor.quit() -> Result<bool, SidecarError>`; Tauri commands implementing `DesktopApi`

Use a PyInstaller `onedir` build, not `onefile`: onefile starts a bootloader child that can outlive a naive parent kill on Windows. The onedir engine must not spawn grandchildren. Rust retains the one `std::process::Child`; Python also exits on desktop stdin EOF and handles SIGINT/SIGTERM, so graceful and abrupt native shutdown both end the app-owned process tree.

Native bundles are built on their matching host because PyInstaller and Tauri are not general cross-compilers:

| Host runner | Rust target | Tauri bundles | Staged engine |
|---|---|---|---|
| Apple Silicon macOS | `aarch64-apple-darwin` | `.app`, `.dmg` | resource directory `engine/alphaloop-engine` with sibling `_internal/` |
| Windows x64 | `x86_64-pc-windows-msvc` | `.msi`, NSIS `.exe` | resource directory `engine/alphaloop-engine.exe` with sibling `_internal/` |
| Linux x64 | `x86_64-unknown-linux-gnu` | `.deb`, `.AppImage` | resource directory `engine/alphaloop-engine` with sibling `_internal/` |

The GUI never installs launchd, systemd, a Windows Service, a scheduled task, or a login item. Native last-window close and app Quit kill only a desktop-owned child. If the handshake says an existing CLI owner is running, the app attaches to it and never kills it. Browser unload has no native lifecycle event and therefore cannot stop a CLI-owned engine.

- [ ] **Step 1: Write the failing ownership and idempotent-shutdown Rust test**

Create `apps/desktop/src-tauri/tests/sidecar_lifecycle.rs`:

```rust
use std::sync::{
    atomic::{AtomicUsize, Ordering},
    Arc,
};

use alphaloop_desktop::{
    EngineOwner, EngineSupervisor, ManagedChild, OwnerRecord,
};

struct FakeChild {
    kills: Arc<AtomicUsize>,
}

impl ManagedChild for FakeChild {
    fn pid(&self) -> u32 {
        4321
    }

    fn kill(self: Box<Self>) -> Result<(), String> {
        self.kills.fetch_add(1, Ordering::SeqCst);
        Ok(())
    }
}

fn owner(owner: EngineOwner) -> OwnerRecord {
    OwnerRecord {
        protocol_version: 1,
        owner,
        pid: 4321,
        endpoint: "http://127.0.0.1:46321".into(),
        auth_token: "test-token".into(),
    }
}

#[test]
fn last_window_close_kills_owned_sidecar_exactly_once() {
    let kills = Arc::new(AtomicUsize::new(0));
    let supervisor = EngineSupervisor::default();
    supervisor
        .adopt_owned(
            Box::new(FakeChild {
                kills: kills.clone(),
            }),
            owner(EngineOwner::Desktop),
        )
        .unwrap();

    assert_eq!(supervisor.close_last_window().unwrap(), true);
    assert_eq!(supervisor.quit().unwrap(), false);
    assert_eq!(kills.load(Ordering::SeqCst), 1);
}

#[test]
fn app_quit_kills_owned_sidecar_exactly_once() {
    let kills = Arc::new(AtomicUsize::new(0));
    let supervisor = EngineSupervisor::default();
    supervisor
        .adopt_owned(
            Box::new(FakeChild {
                kills: kills.clone(),
            }),
            owner(EngineOwner::Desktop),
        )
        .unwrap();

    assert_eq!(supervisor.quit().unwrap(), true);
    assert_eq!(supervisor.quit().unwrap(), false);
    assert_eq!(kills.load(Ordering::SeqCst), 1);
}

#[test]
fn attached_cli_owner_is_never_killed_by_desktop() {
    let supervisor = EngineSupervisor::default();
    supervisor.attach(owner(EngineOwner::Cli)).unwrap();

    assert_eq!(supervisor.close_last_window().unwrap(), false);
    assert_eq!(supervisor.quit().unwrap(), false);
    assert_eq!(supervisor.snapshot().owner(), Some(EngineOwner::Cli));
}

#[test]
fn a_second_binding_is_rejected() {
    let supervisor = EngineSupervisor::default();
    supervisor.attach(owner(EngineOwner::Cli)).unwrap();
    let error = supervisor.attach(owner(EngineOwner::Desktop)).unwrap_err();
    assert_eq!(error, "engine supervisor already bound");
}

#[test]
fn closing_one_of_multiple_windows_does_not_call_shutdown() {
    let kills = Arc::new(AtomicUsize::new(0));
    let supervisor = EngineSupervisor::default();
    supervisor
        .adopt_owned(
            Box::new(FakeChild {
                kills: kills.clone(),
            }),
            owner(EngineOwner::Desktop),
        )
        .unwrap();

    assert_eq!(supervisor.window_close_requested(2).unwrap(), false);
    assert_eq!(kills.load(Ordering::SeqCst), 0);
}

#[test]
fn browser_tab_close_has_no_supervisor_event() {
    let public_events = ["last_native_window_closed", "native_app_quit"];
    assert!(!public_events.contains(&"browser_unload"));
}
```

- [ ] **Step 2: Run the Tauri lifecycle test and verify RED**

Run: `cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --test sidecar_lifecycle`

Expected: FAIL because `apps/desktop/src-tauri/Cargo.toml` does not exist.

- [ ] **Step 3: Implement the native supervisor, Tauri event binding, packaging config, and target staging**

Create `apps/desktop/src-tauri/Cargo.toml`:

```toml
[package]
name = "alphaloop-desktop"
version = "0.2.0"
description = "alphaloop local-first research desktop"
edition = "2021"

[lib]
name = "alphaloop_desktop"
crate-type = ["staticlib", "cdylib", "rlib"]

[build-dependencies]
tauri-build = { version = "2" }

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tauri = { version = "2" }
tauri-plugin-notification = "2"
reqwest = { version = "0.12", features = ["json"] }
```

Create `apps/desktop/src-tauri/build.rs`:

```rust
fn main() {
    tauri_build::build();
}
```

Create `apps/desktop/src-tauri/src/sidecar.rs`:

```rust
use std::sync::Mutex;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum EngineOwner {
    Desktop,
    Cli,
}

#[derive(Debug, Clone, PartialEq, Eq, Deserialize, Serialize)]
pub struct OwnerRecord {
    pub protocol_version: u16,
    pub owner: EngineOwner,
    pub pid: u32,
    pub endpoint: String,
    pub auth_token: String,
}

pub trait ManagedChild: Send {
    fn pid(&self) -> u32;
    fn kill(self: Box<Self>) -> Result<(), String>;
}

enum Binding {
    Stopped,
    Owned {
        child: Box<dyn ManagedChild>,
        owner: OwnerRecord,
    },
    Attached(OwnerRecord),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BindingSnapshot {
    Stopped,
    Owned(OwnerRecord),
    Attached(OwnerRecord),
}

impl BindingSnapshot {
    pub fn owner(&self) -> Option<EngineOwner> {
        match self {
            Self::Stopped => None,
            Self::Owned(record) | Self::Attached(record) => Some(record.owner),
        }
    }
}

pub type SidecarError = String;

pub struct EngineSupervisor {
    binding: Mutex<Binding>,
}

impl Default for EngineSupervisor {
    fn default() -> Self {
        Self {
            binding: Mutex::new(Binding::Stopped),
        }
    }
}

impl EngineSupervisor {
    pub fn adopt_owned(
        &self,
        child: Box<dyn ManagedChild>,
        owner: OwnerRecord,
    ) -> Result<(), SidecarError> {
        if owner.owner != EngineOwner::Desktop || child.pid() != owner.pid {
            return Err("owned child does not match desktop handshake".into());
        }
        let mut binding = self.binding.lock().map_err(|_| "supervisor lock poisoned")?;
        if !matches!(*binding, Binding::Stopped) {
            return Err("engine supervisor already bound".into());
        }
        *binding = Binding::Owned { child, owner };
        Ok(())
    }

    pub fn attach(&self, owner: OwnerRecord) -> Result<(), SidecarError> {
        let mut binding = self.binding.lock().map_err(|_| "supervisor lock poisoned")?;
        if !matches!(*binding, Binding::Stopped) {
            return Err("engine supervisor already bound".into());
        }
        *binding = Binding::Attached(owner);
        Ok(())
    }

    pub fn snapshot(&self) -> BindingSnapshot {
        let binding = self.binding.lock().expect("supervisor lock poisoned");
        match &*binding {
            Binding::Stopped => BindingSnapshot::Stopped,
            Binding::Owned { owner, .. } => BindingSnapshot::Owned(owner.clone()),
            Binding::Attached(owner) => BindingSnapshot::Attached(owner.clone()),
        }
    }

    pub fn window_close_requested(&self, native_window_count: usize) -> Result<bool, SidecarError> {
        if native_window_count == 1 {
            self.close_last_window()
        } else {
            Ok(false)
        }
    }

    pub fn close_last_window(&self) -> Result<bool, SidecarError> {
        self.shutdown_owned()
    }

    pub fn quit(&self) -> Result<bool, SidecarError> {
        self.shutdown_owned()
    }

    fn shutdown_owned(&self) -> Result<bool, SidecarError> {
        let prior = {
            let mut binding = self.binding.lock().map_err(|_| "supervisor lock poisoned")?;
            std::mem::replace(&mut *binding, Binding::Stopped)
        };
        match prior {
            Binding::Owned { child, .. } => {
                child.kill()?;
                Ok(true)
            }
            Binding::Attached(owner) => {
                let mut binding = self.binding.lock().map_err(|_| "supervisor lock poisoned")?;
                *binding = Binding::Attached(owner);
                Ok(false)
            }
            Binding::Stopped => Ok(false),
        }
    }
}
```

Create `apps/desktop/src-tauri/src/commands.rs`:

```rust
use std::sync::{Arc, Mutex};

use reqwest::Client;
use serde_json::{json, Value};
use tauri::{AppHandle, State};
use tauri_plugin_notification::NotificationExt;

#[derive(Clone)]
struct Connection {
    endpoint: String,
    auth_token: String,
}

#[derive(Clone, Default)]
pub struct EngineConnection {
    connection: Arc<Mutex<Option<Connection>>>,
}

#[derive(Default)]
pub struct NotificationTracker {
    last_event: Mutex<Option<String>>,
}

impl EngineConnection {
    pub fn set(&self, endpoint: String, auth_token: String) -> Result<(), String> {
        let mut connection = self
            .connection
            .lock()
            .map_err(|_| "engine connection lock poisoned")?;
        *connection = Some(Connection {
            endpoint,
            auth_token,
        });
        Ok(())
    }

    async fn post(&self, request: Value) -> Result<Value, String> {
        let connection = self
            .connection
            .lock()
            .map_err(|_| "engine connection lock poisoned")?
            .clone()
            .ok_or("engine is not ready")?;
        Client::new()
            .post(format!("{}/commands", connection.endpoint))
            .bearer_auth(connection.auth_token)
            .json(&request)
            .send()
            .await
            .map_err(|error| error.to_string())?
            .error_for_status()
            .map_err(|error| error.to_string())?
            .json()
            .await
            .map_err(|error| error.to_string())
    }
}

#[tauri::command]
pub async fn fetch_view(
    route: String,
    app: AppHandle,
    connection: State<'_, EngineConnection>,
    tracker: State<'_, NotificationTracker>,
) -> Result<Value, String> {
    let view = connection
        .post(json!({"type": "fetch_view", "route": route}))
        .await?;
    let kind = view["kind"].as_str().unwrap_or_default();
    let status = view["status"].as_str().unwrap_or_default();
    let body = match (kind, status) {
        ("awaiting_confirm", _) => Some("研究需要你确认"),
        ("completed", "completed") => Some("研究已完成"),
        ("completed", "ended") => Some("研究已结束"),
        _ => None,
    };
    if let Some(body) = body {
        let event_id = format!(
            "{}:{}",
            view["researchId"].as_str().unwrap_or_default(),
            status
        );
        let mut last = tracker
            .last_event
            .lock()
            .map_err(|_| "notification tracker lock poisoned")?;
        if last.as_deref() != Some(&event_id) {
            app.notification()
                .builder()
                .title("alphaloop")
                .body(body)
                .show()
                .map_err(|error| error.to_string())?;
            *last = Some(event_id);
        }
    }
    Ok(view)
}

#[tauri::command]
pub async fn create_draft(connection: State<'_, EngineConnection>) -> Result<String, String> {
    let result = connection.post(json!({"type": "create_draft"})).await?;
    result["research_id"]
        .as_str()
        .map(str::to_owned)
        .ok_or("create_draft response omitted research_id".into())
}

#[tauri::command]
pub async fn confirm_run(
    research_id: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "confirm_run", "research_id": research_id}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn send_dialogue(
    research_id: String,
    message: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "send_dialogue", "research_id": research_id, "message": message}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn pause_research(
    research_id: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "pause", "research_id": research_id}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn resume_research(
    research_id: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "resume", "research_id": research_id}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn confirm_modification(
    research_id: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "confirm_modification", "research_id": research_id}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn extend_research(
    research_id: String,
    hours: f64,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({
            "type": "extend_research",
            "research_id": research_id,
            "hours": hours
        }))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn delete_research(
    research_id: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "delete_research", "research_id": research_id}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn resolve_confirm(
    research_id: String,
    decision: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({
            "type": "resolve_confirm",
            "research_id": research_id,
            "decision": decision
        }))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn export_artifact(
    research_id: String,
    kind: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({"type": "export_artifact", "research_id": research_id, "kind": kind}))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn reverify(
    research_id: String,
    round_id: String,
    method_id: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({
            "type": "reverify",
            "research_id": research_id,
            "round_id": round_id,
            "method_id": method_id
        }))
        .await
        .map(|_| ())
}

#[tauri::command]
pub async fn revise_method(
    method_id: String,
    definition: String,
    connection: State<'_, EngineConnection>,
) -> Result<(), String> {
    connection
        .post(json!({
            "type": "revise_method",
            "method_id": method_id,
            "definition": definition
        }))
        .await
        .map(|_| ())
}
```

Create `apps/desktop/src-tauri/src/lib.rs`:

```rust
mod commands;
mod sidecar;

pub use sidecar::{
    BindingSnapshot, EngineOwner, EngineSupervisor, ManagedChild, OwnerRecord, SidecarError,
};

use std::{
    io::{BufRead, BufReader},
    process::{Child, Command, Stdio},
    sync::Arc,
    thread,
};

use serde::Deserialize;
use tauri::{Manager, RunEvent, WindowEvent};

use commands::EngineConnection;
use commands::NotificationTracker;

struct TauriChild(Child);

impl ManagedChild for TauriChild {
    fn pid(&self) -> u32 {
        self.0.id()
    }

    fn kill(mut self: Box<Self>) -> Result<(), String> {
        self.0.kill().map_err(|error| error.to_string())?;
        self.0.wait().map_err(|error| error.to_string())?;
        Ok(())
    }
}

#[derive(Deserialize)]
struct Handshake {
    protocol_version: u16,
    status: String,
    owner: EngineOwner,
    pid: u32,
    endpoint: String,
    auth_token: String,
}

fn start_desktop_sidecar(
    app: tauri::AppHandle,
    supervisor: Arc<EngineSupervisor>,
    connection: EngineConnection,
) -> Result<(), String> {
    let resource_dir = app.path().resource_dir().map_err(|error| error.to_string())?;
    let executable = resource_dir
        .join("engine")
        .join(if cfg!(windows) {
            "alphaloop-engine.exe"
        } else {
            "alphaloop-engine"
        });
    let mut child = Command::new(executable)
        .args(["--owner", "desktop"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| error.to_string())?;
    let stderr = child.stderr.take().ok_or("engine stderr was not piped")?;
    thread::spawn(move || {
        for line in BufReader::new(stderr).lines().map_while(Result::ok) {
            eprintln!("alphaloop-engine stderr: {line}");
        }
    });
    let stdout = child.stdout.take().ok_or("engine stdout was not piped")?;
    let mut lines = BufReader::new(stdout).lines();
    let first = lines
        .next()
        .ok_or("engine exited before handshake")?
        .map_err(|error| error.to_string())?;
    let handshake: Handshake = match serde_json::from_str(&first) {
        Ok(handshake) => handshake,
        Err(error) => {
            child.kill().map_err(|kill_error| kill_error.to_string())?;
            return Err(error.to_string());
        }
    };
    if handshake.protocol_version != 1 {
        child.kill().map_err(|error| error.to_string())?;
        return Err("engine protocol version mismatch".into());
    }
    let owner = OwnerRecord {
        protocol_version: handshake.protocol_version,
        owner: handshake.owner,
        pid: handshake.pid,
        endpoint: handshake.endpoint.clone(),
        auth_token: handshake.auth_token.clone(),
    };
    connection.set(handshake.endpoint, handshake.auth_token)?;
    match handshake.status.as_str() {
        "ready" => supervisor.adopt_owned(Box::new(TauriChild(child)), owner)?,
        "already_running" => {
            if owner.owner != EngineOwner::Cli {
                child.kill().map_err(|error| error.to_string())?;
                return Err("another desktop instance already owns the engine".into());
            }
            supervisor.attach(owner)?;
            child.wait().map_err(|error| error.to_string())?;
        }
        _ => {
            child.kill().map_err(|error| error.to_string())?;
            return Err("unknown engine handshake status".into());
        }
    }
    thread::spawn(move || {
        for line in lines {
            if let Ok(line) = line {
                eprintln!("alphaloop-engine: {line}");
            }
        }
    });
    Ok(())
}

pub fn run() {
    let supervisor = Arc::new(EngineSupervisor::default());
    let connection = EngineConnection::default();
    let setup_supervisor = supervisor.clone();
    let setup_connection = connection.clone();
    let window_supervisor = supervisor.clone();
    let exit_supervisor = supervisor.clone();
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .manage(supervisor.clone())
        .manage(connection)
        .manage(NotificationTracker::default())
        .invoke_handler(tauri::generate_handler![
            commands::fetch_view,
            commands::create_draft,
            commands::confirm_run,
            commands::send_dialogue,
            commands::pause_research,
            commands::resume_research,
            commands::confirm_modification,
            commands::extend_research,
            commands::delete_research,
            commands::resolve_confirm,
            commands::export_artifact,
            commands::reverify,
            commands::revise_method,
        ])
        .setup(move |app| {
            let handle = app.handle().clone();
            let sidecar = setup_supervisor.clone();
            let engine_connection = setup_connection.clone();
            if let Err(error) = start_desktop_sidecar(handle, sidecar, engine_connection) {
                eprintln!("alphaloop sidecar startup failed: {error}");
            }
            Ok(())
        })
        .on_window_event(move |window, event| {
            if matches!(event, WindowEvent::CloseRequested { .. }) {
                let count = window.app_handle().webview_windows().len();
                if let Err(error) = window_supervisor.window_close_requested(count) {
                    eprintln!("alphaloop sidecar close failed: {error}");
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("failed to build alphaloop desktop");
    app.run(move |_handle, event| {
        if matches!(event, RunEvent::ExitRequested { .. }) {
            if let Err(error) = exit_supervisor.quit() {
                eprintln!("alphaloop sidecar quit failed: {error}");
            }
        }
    });
}
```

Create `apps/desktop/src-tauri/src/main.rs`:

```rust
fn main() {
    alphaloop_desktop::run();
}
```

Create `apps/desktop/src-tauri/tauri.conf.json`:

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "alphaloop",
  "version": "0.2.0",
  "identifier": "ai.alphastrategy.alphaloop",
  "build": {
    "beforeDevCommand": "npm run dev",
    "devUrl": "http://localhost:1420",
    "beforeBuildCommand": "npm run build",
    "frontendDist": "../dist"
  },
  "app": {
    "windows": [
      {
        "label": "main",
        "title": "alphaloop",
        "width": 1440,
        "height": 900,
        "minWidth": 1180,
        "minHeight": 720
      }
    ],
    "security": {"csp": "default-src 'self'; connect-src 'self' ipc: http://ipc.localhost"}
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "resources": {
      "resources/engine/**/*": "engine/"
    }
  }
}
```

Create `apps/desktop/src-tauri/capabilities/default.json`:

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "description": "Main alphaloop webview; process spawn is Rust-owned.",
  "windows": ["main"],
  "permissions": ["core:default", "notification:default"]
}
```

Create `packaging/alphaloop-engine.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("engine")
analysis = Analysis(
    ["engine/main.py"],
    pathex=["."],
    binaries=[],
    datas=[("contracts", "contracts")],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="alphaloop-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
collect = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="alphaloop-engine",
)
```

Create `scripts/stage_sidecar.py`:

```python
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def stage(target: str, source: Path, tauri_root: Path) -> None:
    executable_name = "alphaloop-engine.exe" if "windows" in target else "alphaloop-engine"
    source_executable = source / executable_name
    if not source_executable.is_file():
        raise FileNotFoundError(source_executable)
    destination = tauri_root / "resources" / "engine"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    staged_executable = destination / executable_name
    staged_executable.chmod(staged_executable.stat().st_mode | 0o111)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--source", type=Path, default=Path("dist/alphaloop-engine"))
    parser.add_argument(
        "--tauri-root",
        type=Path,
        default=Path("apps/desktop/src-tauri"),
    )
    args = parser.parse_args()
    stage(args.target, args.source, args.tauri_root)


if __name__ == "__main__":
    main()
```

Replace `apps/desktop/src/main.tsx` with the complete Tauri-aware bootstrap; Vite keeps a no-op preview adapter and never owns or stops an engine:

```tsx
import "@fontsource/noto-serif/500.css";
import "@fontsource/noto-serif-sc/500.css";
import "@fontsource/noto-sans-sc/400.css";
import "@fontsource/ibm-plex-mono/400.css";
import {invoke} from "@tauri-apps/api/core";
import {StrictMode} from "react";
import {createRoot} from "react-dom/client";

import {App} from "./App";
import type {DesktopApi, DesktopView} from "./contracts";

const desktopApi: DesktopApi = {
  async fetchView(route) { return invoke<DesktopView>("fetch_view", {route}); },
  async createDraft() { return invoke<string>("create_draft"); },
  async confirmRun(researchId) { await invoke("confirm_run", {researchId}); },
  async sendDialogue(researchId, message) { await invoke("send_dialogue", {researchId, message}); },
  async pauseResearch(researchId) { await invoke("pause_research", {researchId}); },
  async resumeResearch(researchId) { await invoke("resume_research", {researchId}); },
  async confirmModification(researchId) { await invoke("confirm_modification", {researchId}); },
  async extendResearch(researchId, hours) { await invoke("extend_research", {researchId, hours}); },
  async deleteResearch(researchId) { await invoke("delete_research", {researchId}); },
  async resolveConfirm(researchId, decision) { await invoke("resolve_confirm", {researchId, decision}); },
  async exportArtifact(researchId, kind) { await invoke("export_artifact", {researchId, kind}); },
  async reverify(researchId, roundId, methodId) {
    await invoke("reverify", {researchId, roundId, methodId});
  },
  async reviseMethod(methodId, definition) { await invoke("revise_method", {methodId, definition}); },
};

const previewApi: DesktopApi = {
  async fetchView() { return preview; },
  async createDraft() { return "preview-draft"; },
  async confirmRun() { return undefined; },
  async sendDialogue() { return undefined; },
  async pauseResearch() { return undefined; },
  async resumeResearch() { return undefined; },
  async confirmModification() { return undefined; },
  async extendResearch() { return undefined; },
  async deleteResearch() { return undefined; },
  async resolveConfirm() { return undefined; },
  async exportArtifact() { return undefined; },
  async reverify() { return undefined; },
  async reviseMethod() { return undefined; },
};

const preview: DesktopView = {kind: "research_list", rows: []};
const api = "__TAURI_INTERNALS__" in window ? desktopApi : previewApi;
createRoot(document.getElementById("root")!).render(
  <StrictMode><App api={api} initialView={preview} /></StrictMode>,
);
```

- [ ] **Step 4: Run lifecycle checks and build all native targets on their matching hosts**

Run on Apple Silicon macOS:

```bash
python -m PyInstaller --clean --noconfirm packaging/alphaloop-engine.spec
python scripts/stage_sidecar.py --target aarch64-apple-darwin
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets
cargo clippy --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets -- -D warnings
npm --prefix apps/desktop run tauri -- build --target aarch64-apple-darwin --bundles app,dmg
```

Run in Windows PowerShell:

```powershell
py -m PyInstaller --clean --noconfirm packaging/alphaloop-engine.spec
py scripts/stage_sidecar.py --target x86_64-pc-windows-msvc
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets
cargo clippy --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets -- -D warnings
npm --prefix apps/desktop run tauri -- build --target x86_64-pc-windows-msvc --bundles msi,nsis
```

Run on Linux x64:

```bash
python -m PyInstaller --clean --noconfirm packaging/alphaloop-engine.spec
python scripts/stage_sidecar.py --target x86_64-unknown-linux-gnu
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets
cargo clippy --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets -- -D warnings
npm --prefix apps/desktop run tauri -- build --target x86_64-unknown-linux-gnu --bundles deb,appimage
```

Expected: Rust tests PASS with `6 passed`; Clippy exits `0`; each native package contains the complete `engine/` onedir resource with executable and sibling `_internal/`. Manual smoke checks on each host: desktop starts one child, closing a non-last window leaves it running, closing the last window kills it, app Quit kills it, a second desktop does not double-start, a desktop attached to a CLI owner does not kill that owner, and closing a Vite browser tab leaves the CLI owner running. Verify the nested engine signature before release with `codesign --verify --deep --strict` on macOS and `signtool verify /pa` on Windows; build Linux on the oldest supported glibc image and inspect with `ldd`.

- [ ] **Step 5: Commit native lifecycle and packaging**

```bash
git add apps/desktop/src-tauri apps/desktop/src/main.tsx packaging/alphaloop-engine.spec scripts/stage_sidecar.py
git commit -m "feat(desktop): bind sidecar to native app lifecycle"
```

### Task 12: Headless Engine Ownership and Two-Command CLI

**Files:**
- Create: `apps/__init__.py`
- Create: `apps/cli/__init__.py`
- Create: `apps/cli/main.py`
- Create: `engine/main.py`
- Modify: `engine/research/runtime.py`
- Modify: `engine/research/store.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `RuntimePaths.default()`; `EngineLock.acquire(paths, owner)`; `read_live_owner(paths)`; `SQLiteStore.heartbeat(...)`; `ResearchLoop.run_once(...)`
- Produces: `build_parser() -> argparse.ArgumentParser` with exactly `start` and `status`; `get_status(paths: RuntimePaths) -> EngineStatus`; `run(argv: Sequence[str], paths: RuntimePaths, launcher: Launcher, output: TextIO) -> int`; internal `alphaloop-engine --owner desktop|cli`; ready/already-running handshake consumed by Tauri

CLI `start` is the only supported way to own long-running research without the native app. It launches a detached `cli` owner and exits after the ready handshake. `status` is read-only and prints whether the engine is alive, which owner holds it, whether any research is running, and whether any research awaits confirmation. A CLI start never steals a desktop lock; concurrent starts may spawn contenders, but exactly one engine acquires the lifetime lock and the others report `already_running`.

- [ ] **Step 1: Write the failing parser, status-redaction, idempotency, and lock tests**

Create `tests/test_cli.py`:

```python
import argparse
import io
import json
import multiprocessing
from datetime import UTC, datetime
from pathlib import Path

from apps.cli.main import Launcher, build_parser, get_status, run
from engine.research.runtime import EngineLock, RuntimePaths
from engine.research.store import SQLiteStore

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def paths(root: Path) -> RuntimePaths:
    return RuntimePaths(root, root / "engine.lock", root / "owner.json")


class HoldingLauncher(Launcher):
    def __init__(self, paths: RuntimePaths) -> None:
        self.paths = paths
        self.calls = 0
        self.lock: EngineLock | None = None

    def start(self, owner: str) -> None:
        self.calls += 1
        self.lock = EngineLock.acquire(self.paths, "cli")
        SQLiteStore(self.paths.database_file).heartbeat(self.lock.owner, NOW)


def parser_commands(parser: argparse.ArgumentParser) -> set[str]:
    action = next(
        item
        for item in parser._actions
        if isinstance(item, argparse._SubParsersAction)
    )
    return set(action.choices)


def test_cli_surface_is_exactly_start_and_status() -> None:
    assert parser_commands(build_parser()) == {"start", "status"}


def test_status_reports_stopped_with_stable_json(tmp_path: Path) -> None:
    result = get_status(paths(tmp_path))
    assert result.running is False
    assert result.owner is None
    assert result.pid is None
    assert result.has_running_research is False
    assert result.awaiting_confirm is False


def test_start_is_idempotent_and_status_redacts_runtime_secrets(tmp_path: Path) -> None:
    runtime = paths(tmp_path)
    launcher = HoldingLauncher(runtime)
    output = io.StringIO()

    assert run(["start"], runtime, launcher, output) == 0
    assert run(["start"], runtime, launcher, output) == 0

    lines = [json.loads(line) for line in output.getvalue().splitlines()]
    assert launcher.calls == 1
    assert lines[-1]["running"] is True
    assert lines[-1]["owner"] == "cli"
    assert "endpoint" not in lines[-1]
    assert "auth_token" not in lines[-1]
    assert launcher.lock is not None
    launcher.lock.close()


def test_cli_start_does_not_replace_desktop_owner(tmp_path: Path) -> None:
    runtime = paths(tmp_path)
    desktop = EngineLock.acquire(runtime, "desktop")
    launcher = HoldingLauncher(runtime)
    output = io.StringIO()

    assert run(["start"], runtime, launcher, output) == 0
    assert launcher.calls == 0
    assert json.loads(output.getvalue())["owner"] == "desktop"
    desktop.close()


def contend(root: str, queue: multiprocessing.Queue) -> None:
    runtime = paths(Path(root))
    try:
        lock = EngineLock.acquire(runtime, "cli")
    except RuntimeError:
        queue.put(False)
    else:
        queue.put(True)
        import time
        time.sleep(0.3)
        lock.close()


def test_two_processes_cannot_own_the_engine_together(tmp_path: Path) -> None:
    queue: multiprocessing.Queue = multiprocessing.Queue()
    first = multiprocessing.Process(target=contend, args=(str(tmp_path), queue))
    second = multiprocessing.Process(target=contend, args=(str(tmp_path), queue))
    first.start()
    second.start()
    first.join()
    second.join()
    assert sorted([queue.get(), queue.get()]) == [False, True]
```

- [ ] **Step 2: Run the CLI test and verify RED**

Run: `python -m pytest tests/test_cli.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'apps'`.

- [ ] **Step 3: Implement detached start, redacted status, lock publication, signal handling, and desktop EOF shutdown**

Create `apps/__init__.py`:

```python
"""alphaloop clients."""
```

Create `apps/cli/__init__.py`:

```python
"""Two-command headless client."""
```

Replace `engine/research/runtime.py` with this complete final ownership implementation:

```python
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

import portalocker
from platformdirs import user_runtime_path

OwnerKind = Literal["desktop", "cli"]


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    root: Path
    lock_file: Path
    owner_file: Path

    @property
    def database_file(self) -> Path:
        return self.root / "research.db"

    @property
    def engine_log(self) -> Path:
        return self.root / "engine.log"

    @classmethod
    def default(cls) -> Self:
        root = Path(user_runtime_path("alphaloop", ensure_exists=True))
        return cls(root, root / "engine.lock", root / "owner.json")


@dataclass(frozen=True, slots=True)
class OwnerRecord:
    owner: OwnerKind
    pid: int
    started_at: str
    phase: Literal["starting", "ready"] = "starting"
    endpoint: str | None = None
    auth_token: str | None = None


@dataclass(slots=True)
class EngineLock:
    paths: RuntimePaths
    owner: OwnerRecord
    _handle: object

    @classmethod
    def acquire(cls, paths: RuntimePaths, owner: OwnerKind) -> Self:
        paths.root.mkdir(parents=True, exist_ok=True)
        handle = open(paths.lock_file, "a+", encoding="utf-8")
        try:
            portalocker.lock(handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except portalocker.LockException:
            handle.close()
            raise RuntimeError("alphaloop engine already has an owner")
        record = OwnerRecord(owner, os.getpid(), datetime.now(UTC).isoformat())
        temporary = paths.owner_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(record), sort_keys=True), encoding="utf-8")
        os.replace(temporary, paths.owner_file)
        return cls(paths, record, handle)

    def close(self) -> None:
        if not getattr(self._handle, "closed", True):
            portalocker.unlock(self._handle)
            self._handle.close()
        self.paths.owner_file.unlink(missing_ok=True)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def read_live_owner(paths: RuntimePaths) -> OwnerRecord | None:
    if not paths.owner_file.exists():
        return None
    probe = open(paths.lock_file, "a+", encoding="utf-8")
    try:
        portalocker.lock(probe, portalocker.LOCK_EX | portalocker.LOCK_NB)
    except portalocker.LockException:
        payload = json.loads(paths.owner_file.read_text(encoding="utf-8"))
        return OwnerRecord(**payload)
    else:
        portalocker.unlock(probe)
        paths.owner_file.unlink(missing_ok=True)
        return None
    finally:
        probe.close()


def publish_ready(
    lock: EngineLock,
    endpoint: str,
    auth_token: str,
) -> OwnerRecord:
    ready = replace(
        lock.owner,
        phase="ready",
        endpoint=endpoint,
        auth_token=auth_token,
    )
    temporary = lock.paths.owner_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(ready), sort_keys=True), encoding="utf-8")
    os.replace(temporary, lock.paths.owner_file)
    lock.owner = ready
    return ready
```

Replace `engine/research/store.py` with this complete final store:

```python
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cattrs

from engine.research.models import Attempt, Research
from engine.research.runtime import OwnerRecord

CONVERTER = cattrs.Converter()
CONVERTER.register_unstructure_hook(datetime, lambda value: value.isoformat())
CONVERTER.register_structure_hook(datetime, lambda value, _: datetime.fromisoformat(value))
CONVERTER.register_unstructure_hook(Path, str)
CONVERTER.register_structure_hook(Path, lambda value, _: Path(value))

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS researches (
    research_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_completed_round INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS engine_heartbeat (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    owner TEXT NOT NULL,
    pid INTEGER NOT NULL,
    heartbeat_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_attempts (
    attempt_id TEXT PRIMARY KEY,
    research_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    attempt_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS method_revisions (
    method_id TEXT NOT NULL,
    revision_hash TEXT NOT NULL,
    definition TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (method_id, revision_hash)
);
CREATE TABLE IF NOT EXISTS engine_errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_id TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class Heartbeat:
    owner: str
    pid: int
    heartbeat_at: datetime


class ConcurrentWrite(RuntimeError):
    """The stored research changed after it was loaded."""


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.executescript(SCHEMA)

    @staticmethod
    def _encode(research: Research) -> str:
        return json.dumps(CONVERTER.unstructure(research), sort_keys=True)

    @staticmethod
    def _decode(payload: str) -> Research:
        return CONVERTER.structure(json.loads(payload), Research)

    def create(self, research: Research) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO researches(research_id,state_json,updated_at) VALUES(?,?,?)",
                (research.research_id, self._encode(research), research.updated_at.isoformat()),
            )

    def load(self, research_id: str) -> Research:
        row = self.connection.execute(
            "SELECT state_json FROM researches WHERE research_id=?",
            (research_id,),
        ).fetchone()
        if row is None:
            raise KeyError(research_id)
        return self._decode(row[0])

    def save(self, research: Research, expected_updated_at: datetime) -> None:
        completed = sum(len(version.rounds) for version in research.versions)
        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE researches
                   SET state_json=?, updated_at=?, last_completed_round=?
                 WHERE research_id=? AND updated_at=?
                """,
                (
                    self._encode(research),
                    research.updated_at.isoformat(),
                    completed,
                    research.research_id,
                    expected_updated_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                raise ConcurrentWrite(research.research_id)

    def last_completed_round(self, research_id: str) -> int:
        row = self.connection.execute(
            "SELECT last_completed_round FROM researches WHERE research_id=?",
            (research_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    def record_review_attempt(
        self,
        research_id: str,
        version_number: int,
        round_number: int,
        attempt: Attempt,
        now: datetime,
    ) -> None:
        if attempt.review is None:
            raise ValueError("review attempt must contain ReviewReport")
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO review_attempts(
                    attempt_id,research_id,version_number,round_number,
                    passed,attempt_json,created_at
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    attempt.attempt_id,
                    research_id,
                    version_number,
                    round_number,
                    int(attempt.review.passed),
                    json.dumps(CONVERTER.unstructure(attempt), sort_keys=True),
                    now.isoformat(),
                ),
            )

    def review_failure_count(
        self,
        research_id: str,
        version_number: int,
        round_number: int,
    ) -> int:
        row = self.connection.execute(
            """
            SELECT COUNT(*) FROM review_attempts
             WHERE research_id=? AND version_number=? AND round_number=? AND passed=0
            """,
            (research_id, version_number, round_number),
        ).fetchone()
        return int(row[0])

    def heartbeat(self, owner: OwnerRecord, now: datetime) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO engine_heartbeat(singleton,owner,pid,heartbeat_at)
                VALUES(1,?,?,?)
                ON CONFLICT(singleton) DO UPDATE SET
                    owner=excluded.owner,pid=excluded.pid,heartbeat_at=excluded.heartbeat_at
                """,
                (owner.owner, owner.pid, now.isoformat()),
            )

    def read_heartbeat(self) -> Heartbeat:
        row = self.connection.execute(
            "SELECT owner,pid,heartbeat_at FROM engine_heartbeat WHERE singleton=1"
        ).fetchone()
        if row is None:
            raise LookupError("heartbeat unavailable")
        return Heartbeat(row[0], int(row[1]), datetime.fromisoformat(row[2]))

    def status_flags(self) -> tuple[bool, bool]:
        rows = self.connection.execute("SELECT state_json FROM researches").fetchall()
        states = [json.loads(row[0])["status"] for row in rows]
        return "running" in states, "awaiting_confirm" in states

    def list_research(self) -> tuple[Research, ...]:
        rows = self.connection.execute(
            "SELECT state_json FROM researches ORDER BY updated_at DESC"
        ).fetchall()
        return tuple(self._decode(row[0]) for row in rows)

    def list_methods(self) -> tuple[tuple[str, str, str], ...]:
        rows = self.connection.execute(
            """
            SELECT method_id,revision_hash,definition
              FROM method_revisions
             ORDER BY method_id,created_at DESC
            """
        ).fetchall()
        return tuple((row[0], row[1], row[2]) for row in rows)

    def running_ids(self) -> tuple[str, ...]:
        rows = self.connection.execute(
            "SELECT research_id,state_json FROM researches ORDER BY research_id"
        ).fetchall()
        return tuple(
            research_id
            for research_id, payload in rows
            if json.loads(payload)["status"] == "running"
        )

    def delete(self, research_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM researches WHERE research_id=?",
                (research_id,),
            )

    def revise_method(self, method_id: str, definition: str, now: datetime) -> str:
        revision = hashlib.sha256(definition.encode("utf-8")).hexdigest()
        with self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO method_revisions(
                    method_id,revision_hash,definition,created_at
                ) VALUES(?,?,?,?)
                """,
                (method_id, revision, definition, now.isoformat()),
            )
        return revision

    def record_error(self, research_id: str, message: str, now: datetime) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO engine_errors(research_id,message,created_at) VALUES(?,?,?)",
                (research_id, message, now.isoformat()),
            )
```

Create `apps/cli/main.py`:

```python
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, Sequence, TextIO

from engine.research.runtime import (
    OwnerKind,
    RuntimePaths,
    read_live_owner,
)
from engine.research.store import SQLiteStore


@dataclass(frozen=True, slots=True)
class EngineStatus:
    running: bool
    owner: OwnerKind | None
    pid: int | None
    has_running_research: bool
    awaiting_confirm: bool


class Launcher(Protocol):
    def start(self, owner: str) -> None:
        raise NotImplementedError


class DetachedLauncher:
    def __init__(self, paths: RuntimePaths) -> None:
        self.paths = paths

    @staticmethod
    def _command() -> list[str]:
        suffix = ".exe" if os.name == "nt" else ""
        sibling = Path(sys.executable).with_name(f"alphaloop-engine{suffix}")
        if getattr(sys, "frozen", False) and sibling.is_file():
            return [str(sibling)]
        return [sys.executable, "-m", "engine.main"]

    def start(self, owner: str) -> None:
        self.paths.root.mkdir(parents=True, exist_ok=True)
        log = open(self.paths.engine_log, "ab", buffering=0)
        kwargs: dict[str, object] = {
            "stdin": subprocess.DEVNULL,
            "stdout": log,
            "stderr": log,
            "close_fds": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_NO_WINDOW
            )
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(self._command() + ["--owner", owner], **kwargs)
        log.close()
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            record = read_live_owner(self.paths)
            if (
                record is not None
                and record.phase == "ready"
                and record.endpoint
                and record.auth_token
            ):
                return
            time.sleep(0.05)
        process.terminate()
        process.wait(timeout=5.0)
        raise TimeoutError("alphaloop engine did not publish readiness within 10 seconds")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alphaloop")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("start", help="start or reuse the headless engine")
    commands.add_parser("status", help="show engine and research status")
    return parser


def get_status(paths: RuntimePaths) -> EngineStatus:
    owner = read_live_owner(paths)
    if owner is None:
        return EngineStatus(False, None, None, False, False)
    store = SQLiteStore(paths.database_file)
    running, awaiting = store.status_flags()
    return EngineStatus(True, owner.owner, owner.pid, running, awaiting)


def _public(status: EngineStatus) -> dict[str, object]:
    return asdict(status)


def run(
    argv: Sequence[str],
    paths: RuntimePaths,
    launcher: Launcher,
    output: TextIO,
) -> int:
    command = build_parser().parse_args(argv).command
    if command == "start" and read_live_owner(paths) is None:
        launcher.start("cli")
    status = get_status(paths)
    output.write(json.dumps(_public(status), sort_keys=True) + "\n")
    return 0


def main() -> int:
    paths = RuntimePaths.default()
    return run(sys.argv[1:], paths, DetachedLauncher(paths), sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `engine/main.py`:

```python
from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import sys
import threading
import time
import uuid
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import httpx
import jsonschema
import pandas as pd

from engine.dialogue.intent import interpret
from engine.dialogue.slots import apply_intent
from engine.export import build_strategy_pack
from engine.research.clock import TimeBudget
from engine.research.gather import (
    AkShareDataAdapter,
    LocalMaterialAdapter,
    PapersAdapter,
    RoutingDataAdapter,
    SecEdgarAdapter,
    YahooDataAdapter,
)
from engine.research.loop import DefaultRoundBuilder, ResearchLoop
from engine.research.models import Research, ResearchEvent, Reverification, Slot, new_research
from engine.research.runtime import (
    EngineLock,
    OwnerKind,
    OwnerRecord,
    RuntimePaths,
    publish_ready,
    read_live_owner,
)
from engine.research.state_machine import all_slots_locked, transition
from engine.research.store import CONVERTER, SQLiteStore
from engine.research.simulate import simulate_daily
from engine.review.subagent import LLMPort, OpenAICompatibleLLM, SubagentReviewer
from engine.strategy import MarketPanel, MeanReversionStrategy
from engine.verifiers import run_verifiers

PROTOCOL_VERSION = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alphaloop-engine")
    parser.add_argument("--owner", choices=("desktop", "cli"), required=True)
    return parser


def _handshake(status: str, owner: OwnerRecord) -> None:
    print(
        json.dumps(
            {
                "protocol_version": PROTOCOL_VERSION,
                "status": status,
                "owner": owner.owner,
                "pid": owner.pid,
                "endpoint": owner.endpoint,
                "auth_token": owner.auth_token,
            },
            sort_keys=True,
        ),
        flush=True,
    )


def _watch_desktop_stdin(stop: threading.Event) -> None:
    while sys.stdin.buffer.read(1):
        continue
    stop.set()


class FailClosedLLM(LLMPort):
    def complete(self, system: str, user: str) -> str:
        return json.dumps(
            {
                "passed": False,
                "findings": [
                    {
                        "code": "review_unavailable",
                        "message": "No second-LLM reviewer credentials are configured.",
                    }
                ],
                "required_changes": (
                    "Configure ALPHALOOP_LLM_BASE_URL, "
                    "ALPHALOOP_LLM_API_KEY, and ALPHALOOP_LLM_MODEL."
                ),
            }
        )


def build_loop(store: SQLiteStore, paths: RuntimePaths) -> ResearchLoop:
    client = httpx.Client()
    material_root = paths.root / "materials"
    material_root.mkdir(parents=True, exist_ok=True)
    material_ports = (
        PapersAdapter(client, lambda: datetime.now(UTC)),
        SecEdgarAdapter(
            client,
            lambda: datetime.now(UTC),
            "alphaloop/0.2 research@example.invalid",
        ),
        LocalMaterialAdapter(material_root, lambda: datetime.now(UTC)),
    )
    data_port = RoutingDataAdapter(YahooDataAdapter(), AkShareDataAdapter())
    base_url = os.environ.get("ALPHALOOP_LLM_BASE_URL")
    api_key = os.environ.get("ALPHALOOP_LLM_API_KEY")
    model = os.environ.get("ALPHALOOP_LLM_MODEL")
    llm: LLMPort = (
        OpenAICompatibleLLM(client, base_url, api_key, model)
        if base_url and api_key and model
        else FailClosedLLM()
    )
    today = date.today()
    builder = DefaultRoundBuilder(
        material_ports=material_ports,
        data_port=data_port,
        start=today - timedelta(days=365 * 12),
        end=today,
        snapshot_root=paths.root / "snapshots",
    )
    return ResearchLoop(
        store,
        builder,
        SubagentReviewer(llm),
        TimeBudget(time.monotonic),
        lambda: datetime.now(UTC),
    )


class ResearchCommandService:
    def __init__(self, store: SQLiteStore, paths: RuntimePaths) -> None:
        self.store = store
        self.paths = paths

    def _save(self, before: Research, after: Research) -> None:
        self.store.save(after, before.updated_at)

    @staticmethod
    def _settings(research: Research) -> dict[str, str]:
        brief = research.brief
        return {
            "thesis": str(brief.thesis.value or ""),
            "universe": str(brief.universe.value or ""),
            "max_effective_hours": str(brief.max_effective_hours.value or ""),
            "round1_methods": " · ".join(
                method.method_id for method in (brief.round1_methods.value or ())
            ),
            "coverage_floor": str(brief.coverage_floor.value or ""),
        }

    def view_for(self, route: str) -> dict[str, Any]:
        if route.startswith("#/methods"):
            methods = [
                {
                    "id": method_id,
                    "name": method_id,
                    "revision": revision,
                    "description": definition,
                }
                for method_id, revision, definition in self.store.list_methods()
            ]
            selected = route.removeprefix("#/methods/") if route.startswith("#/methods/") else None
            return {"kind": "methods", "selected": selected, "methods": methods}
        if route == "#/research":
            summaries = [
                {
                    "id": research.research_id,
                    "title": str(research.brief.thesis.value or "新研究"),
                    "status": research.status.value,
                }
                for research in self.store.list_research()
            ]
            awaiting = next(
                (item for item in summaries if item["status"] == "awaiting_confirm"),
                None,
            )
            rows = [item for item in summaries if item is not awaiting]
            return {"kind": "research_list", "awaiting": awaiting, "rows": rows}
        research_id = route.removeprefix("#/research/")
        research = self.store.load(research_id)
        if research.status.value == "draft":
            kind = "confirm_run" if all_slots_locked(research.brief) else "draft"
            return {
                "kind": kind,
                "researchId": research_id,
                "messages": [],
                "settings": self._settings(research),
            }
        if research.status.value in {"running", "paused"}:
            version = research.current_version_number or 1
            rounds = research.versions[version - 1].rounds if research.versions else ()
            return {
                "kind": "running",
                "researchId": research_id,
                "status": research.status.value,
                "version": version,
                "effective": f"{research.effective_seconds / 3600:.2f}h",
                "coverage": str(research.brief.coverage_floor.value or ""),
                "rounds": [round_.accepted_attempt.spec.id for round_ in reversed(rounds)],
            }
        if research.status.value == "awaiting_confirm":
            request = research.pending_confirm
            if request is None:
                raise ValueError("awaiting_confirm research requires ConfirmRequest")
            return {
                "kind": "awaiting_confirm",
                "researchId": research_id,
                "version": research.current_version_number or 1,
                "proposed": request.proposed_change,
                "reason": request.reason,
                "effect": request.effect,
            }
        rounds = research.versions[-1].rounds if research.versions else ()
        selected = rounds[-1] if rounds else None
        return {
            "kind": "completed",
            "researchId": research_id,
            "status": research.status.value,
            "title": str(research.brief.thesis.value or "研究结果"),
            "selectedRoundId": selected.round_id if selected else "",
            "selectedMethodId": "overfit.walk",
            "eligibility": {
                "allMethodsPassed": (
                    selected is not None and selected.accepted_attempt.verification.passed
                ),
                "noPendingConfirm": research.pending_confirm is None,
                "reverifiesPassed": all(
                    item.passed
                    for item in research.reverifications
                    if selected is not None and item.round_id == selected.round_id
                ),
            },
        }

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        kind = request["type"]
        now = datetime.now(UTC)
        if kind == "fetch_view":
            return self.view_for(request["route"])
        if kind == "create_draft":
            research_id = str(uuid.uuid4())
            self.store.create(new_research(research_id, now))
            return {"research_id": research_id}
        if kind == "revise_method":
            revision = self.store.revise_method(
                request["method_id"],
                request["definition"],
                now,
            )
            return {"revision_hash": revision}

        research = self.store.load(request["research_id"])
        if kind == "delete_research":
            self.store.delete(research.research_id)
            return {"research_id": research.research_id, "deleted": True}
        if kind == "send_dialogue":
            updated = apply_intent(
                research,
                interpret(request["message"], research),
                now,
            )
        elif kind == "confirm_run":
            updated = transition(research, ResearchEvent.CONFIRM_RUN, now)
        elif kind == "pause":
            updated = transition(research, ResearchEvent.PAUSE, now)
        elif kind == "resume":
            updated = transition(research, ResearchEvent.RESUME, now)
        elif kind == "confirm_modification":
            updated = transition(research, ResearchEvent.MODIFY_CONFIRM, now)
        elif kind == "extend_research":
            current_hours = research.brief.max_effective_hours.value or 0.0
            extended = replace(
                research,
                brief=replace(
                    research.brief,
                    max_effective_hours=Slot(
                        current_hours + float(request["hours"]),
                        True,
                    ),
                ),
                updated_at=now,
            )
            updated = transition(extended, ResearchEvent.EXTEND_CONFIRM, now)
        elif kind == "resolve_confirm":
            event = {
                "approve_new_version": ResearchEvent.CONFIRM_APPROVE,
                "reject_keep_logic": ResearchEvent.CONFIRM_REJECT,
                "pause_and_edit": ResearchEvent.CONFIRM_PAUSE,
            }[request["decision"]]
            updated = transition(research, event, now)
        elif kind == "reverify":
            matching = [
                round_
                for version in research.versions
                for round_ in version.rounds
                if round_.round_id == request["round_id"]
            ]
            if len(matching) != 1:
                raise ValueError("reverify requires one frozen round_id")
            accepted = matching[0].accepted_attempt
            if accepted.data_snapshot_path is None:
                raise ValueError("reverify requires the selected round's frozen data")
            frozen = pd.read_csv(
                accepted.data_snapshot_path,
                index_col="date",
                parse_dates=True,
            )

            class FrozenDataPort:
                def load_daily(
                    self,
                    symbols: tuple[str, ...],
                    start: date,
                    end: date,
                ) -> pd.DataFrame:
                    if symbols == (accepted.simulation.benchmark_id,):
                        return frozen[["__benchmark__"]].rename(
                            columns={"__benchmark__": accepted.simulation.benchmark_id}
                        )
                    return frozen[list(symbols)]

            rerun_simulation = simulate_daily(
                MeanReversionStrategy(accepted.spec),
                FrozenDataPort(),
                frozen.index.min().date(),
                frozen.index.max().date(),
            )
            rerun = run_verifiers(rerun_simulation, accepted.spec)
            matching_method = [
                result
                for result in rerun.results
                if result.verifier_id == request["method_id"]
            ]
            if len(matching_method) != 1:
                raise ValueError("method_id is not frozen on the selected round")
            record = Reverification(
                round_id=request["round_id"],
                method_id=request["method_id"],
                report=rerun,
                passed=matching_method[0].passed,
                created_at=now,
            )
            with_rerun = replace(
                research,
                reverifications=research.reverifications + (record,),
                updated_at=now,
            )
            updated = transition(
                with_rerun,
                ResearchEvent.REVERIFY_PASS
                if record.passed
                else ResearchEvent.REVERIFY_FAIL,
                now,
            )
        elif kind == "export_artifact":
            export_root = self.paths.root / "exports"
            export_root.mkdir(parents=True, exist_ok=True)
            if request["kind"] == "research_record":
                destination = export_root / f"{research.research_id}-research-record.json"
                destination.write_text(
                    json.dumps(
                        CONVERTER.unstructure(research),
                        sort_keys=True,
                        default=str,
                    ),
                    encoding="utf-8",
                )
                return {"path": str(destination)}
            if not research.versions or not research.versions[-1].rounds:
                raise ValueError("strategy pack requires a completed round")
            attempt = research.versions[-1].rounds[-1].accepted_attempt
            if attempt.data_snapshot_path is None:
                raise ValueError("strategy pack requires a frozen data snapshot")
            prices = pd.read_csv(
                attempt.data_snapshot_path,
                index_col="date",
                parse_dates=True,
            )
            destination = export_root / f"{research.research_id}-strategy-pack.zip"
            build_strategy_pack(
                research,
                MeanReversionStrategy(attempt.spec),
                MarketPanel(prices, now),
                destination,
            )
            return {"path": str(destination)}
        else:
            raise ValueError(f"unknown desktop request type: {kind}")
        self._save(research, updated)
        return {"research_id": research.research_id, "status": updated.status.value}


class EngineApiHandler(BaseHTTPRequestHandler):
    service: ResearchCommandService
    auth_token: str
    request_schema: dict[str, Any]

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:
        if self.path != "/commands":
            self._send(404, {"error": "not_found"})
            return
        if self.headers.get("Authorization") != f"Bearer {self.auth_token}":
            self._send(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            jsonschema.validate(request, self.request_schema)
            self._send(200, self.service.handle(request))
        except (
            ValueError,
            KeyError,
            json.JSONDecodeError,
            jsonschema.ValidationError,
        ) as error:
            self._send(400, {"error": str(error)})

    def log_message(self, format: str, *args: object) -> None:
        return


def start_api(
    service: ResearchCommandService,
    token: str,
) -> tuple[HTTPServer, str]:
    bundle_root = Path(
        getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
    )
    schema = json.loads(
        (bundle_root / "contracts" / "desktop-api.schema.json").read_text(
            encoding="utf-8"
        )
    )
    handler = type(
        "BoundEngineApiHandler",
        (EngineApiHandler,),
        {"service": service, "auth_token": token, "request_schema": schema},
    )
    server = HTTPServer(("127.0.0.1", 0), handler)
    endpoint = f"http://127.0.0.1:{server.server_port}"
    threading.Thread(
        target=server.serve_forever,
        daemon=True,
        name="engine-loopback-api",
    ).start()
    return server, endpoint


def serve(owner_kind: OwnerKind, paths: RuntimePaths) -> int:
    try:
        lock = EngineLock.acquire(paths, owner_kind)
    except RuntimeError:
        deadline = time.monotonic() + 10.0
        owner = read_live_owner(paths)
        while (
            owner is not None
            and (
                owner.phase != "ready"
                or owner.endpoint is None
                or owner.auth_token is None
            )
            and time.monotonic() < deadline
        ):
            time.sleep(0.05)
            owner = read_live_owner(paths)
        if owner is None:
            return 1
        if owner.phase != "ready" or owner.endpoint is None or owner.auth_token is None:
            return 1
        _handshake("already_running", owner)
        return 0

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    store = SQLiteStore(paths.database_file)
    loop = build_loop(store, paths)
    service = ResearchCommandService(SQLiteStore(paths.database_file), paths)
    token = secrets.token_urlsafe(32)
    server, endpoint = start_api(service, token)
    owner = publish_ready(lock, endpoint, token)
    _handshake("ready", owner)
    if owner_kind == "desktop":
        threading.Thread(
            target=_watch_desktop_stdin,
            args=(stop,),
            daemon=True,
            name="desktop-parent-eof",
        ).start()
    try:
        while not stop.wait(1.0):
            for research_id in store.running_ids():
                try:
                    loop.run_once(research_id)
                except Exception as error:
                    store.record_error(research_id, str(error), datetime.now(UTC))
            store.heartbeat(owner, datetime.now(UTC))
    finally:
        server.shutdown()
        server.server_close()
        lock.close()
    return 0


def main() -> int:
    args = build_parser().parse_args()
    return serve(args.owner, RuntimePaths.default())


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI/runtime tests, static checks, and process smoke tests**

Run:

```bash
python -m pytest tests/test_cli.py tests/test_loop_runtime.py -q
python -m ruff check engine apps tests
python -m mypy engine apps
alphaloop status
alphaloop start
alphaloop status
```

Expected: pytest PASS with `12 passed`; Ruff and mypy exit `0`; before `start`, status reports `"running": false`; after `start`, status reports `"running": true` and `"owner": "cli"` without endpoint or token. Start a native desktop while CLI owns the engine and verify the desktop reports attached, then quit it and verify CLI status remains running. Stop the smoke-test CLI owner with SIGTERM by pid after verification; this is test cleanup, not a third public CLI command.

- [ ] **Step 5: Commit the closed CLI surface**

```bash
git add apps/__init__.py apps/cli engine/main.py engine/research/runtime.py engine/research/store.py tests/test_cli.py
git commit -m "feat(cli): add start and status ownership"
```

## End-to-End Acceptance Gate

Run the complete implementation suite after Task 12:

```bash
python -m pytest tests -q
python -m ruff check engine apps tests
python -m mypy engine apps
npm --prefix apps/desktop test
npm --prefix apps/desktop run typecheck
npm --prefix apps/desktop run build
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets
cargo clippy --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets -- -D warnings
```

Expected: every command exits `0`. Then perform these acceptance scenarios with a temporary local database:

1. Enter “美股低波动回归”; public literature and market adapters propose US equity, `SPX`, the four frozen verifier revisions, and a measured coverage floor; explicitly lock all five slots.
2. Confirm-run appears as its own cyan card; confirming creates Version 1, then every automatic attempt records all required market metrics, all five gates, and a second-LLM review.
3. Return three failed reviewer reports and verify there is no successful Round, Version remains unchanged, a review-blocked `ConfirmRequest` appears, state becomes `awaiting_confirm`, and effective time stops.
4. Resume with a passing reviewer; verify a completed Round is committed atomically, crash the process during the next simulation, restart, and verify work resumes after the last completed Round.
5. Export the reference mean-reversion pack, extract it on a machine where alphaloop is not installed, and run `python run_backtest.py`; verify metrics are reproduced from bundled `data/prices.csv` and the reserved execution stub is never called.
6. Check all seven Figma screens at 1440×900: 148px Rail, 148×148 Logo, centered Logo+nav, Night only, awaiting-confirm primary list card, separate confirm-run/awaiting-confirm cards, cyan only on those confirmation semantics, and no order action.
7. On macOS arm64, Windows x64, and Linux x64, start from the desktop and verify last-window close and app Quit stop the owned sidecar with no orphan; start from CLI and verify a browser-tab close leaves it running; verify a second owner cannot acquire the lock.

The implementer should stop and fix the first failing gate. Do not weaken a threshold, skip the reviewer, auto-approve a timeout, change a benchmark, or introduce a third CLI command to make acceptance pass.
