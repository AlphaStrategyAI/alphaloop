---
title: "alphaloop Overnight Research Lab — Refactor Technical Design"
status: "design"
date: "2026-08-18"
related_requirements: "docs/requirements/product-positioning-requirements.md"
supersedes: "docs/plans/v07-hybrid-loop.md as the product-level orchestrator; v0.7 remains the historical DAG design"
---

# alphaloop Overnight Research Lab — Refactor Technical Design

This document maps
[`docs/requirements/product-positioning-requirements.md`](../requirements/product-positioning-requirements.md)
onto the **existing** `src/alphaloop` tree. It is a refactor design, not a
greenfield rewrite. New code is added only where current modules cannot
satisfy the overnight-lab contracts.

Implementation is split into independently testable plans under
`docs/plans/`. This document is the architectural source of truth.
The first executable plan is
`docs/plans/2026-08-18-overnight-lab-phase1-contracts.md`.
Phase 7 continues the research protocol after the single-pass worker
landed in Phase 3. Remaining first-release work is
[`docs/plans/2026-08-19-overnight-lab-remaining-work.md`](2026-08-19-overnight-lab-remaining-work.md).

## 1. Current system versus target

### 1.1 What already exists and must be kept

| Package | Role today | Role after refactor |
| --- | --- | --- |
| `alphaloop.diagnostic` | Six deterministic diagnostics plus LLM judge | **Trust layer.** Hard gates wrap Q1–Q6. `llm_judge` remains narrative scoring only and **cannot** produce `FOUND`. |
| `alphaloop.engineer` | Ten classical factors, `@no_lookahead` | Factor library consumed by the constrained DSL. Not deleted. |
| `alphaloop.data` | Yahoo, AKShare, CCXT, OpenBB | Data adapters. Every run must freeze a content-addressed snapshot around them. |
| `alphaloop.backtest` | Deterministic engine | Candidate evaluation engine. Unchanged public math. |
| `alphaloop.strategies` | Python strategy classes + `Signal.weight` | Implementation backend behind the DSL. LLM must not import or exec these classes directly. |
| `alphaloop.judge` + `calibration` | Report-quality judge and calibration | Optional narrative scorer. Explicitly not a hard gate. |
| `alphaloop.loop` | In-process 6-node DAG (`LoopRunner.run()`) | Temporary adapter. Phase 3 replaces its control flow; persistence helpers are reused then narrowed. |
| `alphaloop.webui` | FastAPI + Vite SPA over `runs/` | Phase 4 control plane UI. Backend stays JSON; frontend ships as packaged static assets. |
| `alphaloop.cli` | `backtest`, `optimize`, `fetch`, `report`, `loop`, `judge` | Keep research utilities. Add `start`, job submit/status, `export`. `loop` becomes a compatibility wrapper that submits a job. |
| `alphaloop.live` | Read-only Alpaca adapter, paper-by-default | **Frozen.** Remain importable for tests, removed from the default public API. Loop, runtime, and protocol **must not** import it. |

### 1.2 Gaps the current code cannot satisfy

1. **Package identity is broken.** `pyproject.toml` still declares
   `openstrategy = "openstrategy.cli:main"` and
   `packages = ["src/openstrategy"]`. There is no `src/openstrategy`.
   `__init__.py` still describes OpenStrategy. `__version__.py` is
   `1.0.0` while `pyproject.toml` is `0.5.0`.
2. **`LoopRunner.run()` is a blocking in-process DAG.** Closing the CLI
   process stops the run. There is no durable job, supervisor, or
   checkpoint resume.
3. **Job status and research outcome are conflated.** Termination letters
   A/B/C/D (`target found` / `all tasks done` / `timeout` / `cost`) are
   not `FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE`. Gate A currently fires
   when any scored DSR meets the target, which can claim success without
   the frozen hard-gate set.
4. **N4 does not compose the real diagnostic package.**
   `loop/aggregator.py:diagnose_task` derives synthetic pass/fail from
   Sharpe/CAGR. That is incompatible with evidence authority.
5. **The planner emits strategy class names**, then the executor can
   instantiate Python strategies. That is arbitrary-code-adjacent and
   violates the constrained DSL rule.
6. **Artifact layout is the v0.7 set** (`manifest.yaml`, `top5.json`,
   `results.parquet`, `report.md`). The overnight lab requires
   `research-spec.yaml`, `trial-ledger.jsonl`, `checkpoints/`,
   `evidence/`, `recommendations.json`, and a dataset snapshot hash that
   fails closed on mismatch.
7. **WebUI auto-launch starts Vite + uvicorn.** End users must have
   Node. The requirement is packaged static assets served by the local
   control plane.
8. **No Strategy Candidate Bundle.** There is no immutable `.asb`
   export, content hash, or conformance fixture. `live/` must not become
   the handoff path.
9. **Hypothesis is a free-form goal string**, not a frozen research
   spec. The loop can keep searching until DSR looks good.

### 1.3 Refactor principle

Do not rewrite diagnostics, factors, data sources, or the backtest
engine. Wrap them behind new contracts, then replace only the
orchestrator (`loop`) and the product surface (`cli` / `webui`).

```text
KEEP     diagnostic, engineer, data, backtest, strategies, judge, calibration
FREEZE   live
WRAP     strategies + engineer  ->  constrained DSL
REPLACE  loop control flow      ->  Job API + supervisor + protocol
EVOLVE   cli, webui, persistence artifacts
ADD      contracts, runtime, protocol, bundle export
```

## 2. Target package layout

New code lives in new packages. Existing packages keep their current
paths unless a later plan proves a file has two responsibilities.

```text
src/alphaloop/
├── contracts/                 # Phase 1 — versioned schemas (no I/O side effects except hash/fs layout helpers)
│   ├── status.py              # JobStatus, ResearchOutcome, derive_research_outcome
│   ├── research_spec.py       # frozen hypothesis + protocol
│   ├── gates.py               # HardGateName, GateEvidence, evaluate_hard_gates
│   ├── artifacts.py           # RunLayout, DatasetRef
│   └── bundle.py              # StrategyCandidateBundle, canonical hash, export guard
├── runtime/                   # Phase 2 — durable local control plane
│   ├── api.py                 # Job API (create, get, cancel, resume)
│   ├── daemon.py              # alphaloop start
│   ├── supervisor.py          # worker lease, heartbeat, restart
│   └── checkpoint.py
├── protocol/                  # Phase 3 — research loop
│   ├── dsl.py                 # constrained strategy DSL, target-weight output
│   ├── stop.py                # epistemic stopping
│   ├── profiles/
│   │   ├── us_equity_daily.py
│   │   └── crypto_daily.py
│   └── loop.py                # iterative loop using contracts + runtime
├── diagnostic/                # KEEP
├── engineer/                  # KEEP
├── data/                      # KEEP
├── backtest/                  # KEEP
├── strategies/                # KEEP, DSL-backed only
├── live/                      # FREEZE, not in default __all__
├── loop/                      # adapter until Phase 3 deletes the blocking runner
├── webui/                     # Phase 4
├── cli/                       # evolve
└── skills/                    # Phase 6 local Agent Skill files
```

Files that change together stay together: all overnight-lab schema types
are in `contracts/`. Runtime never imports `live`. Protocol never
imports `webui`. Bundle export reads contracts + sealed artifacts only.

## 3. Contracts (Phase 1)

All types below are the names later plans must use. Do not invent
parallel enums in `loop` or `webui`.

### 3.1 Job status versus research outcome

```python
from enum import Enum

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ResearchOutcome(str, Enum):
    FOUND = "FOUND"
    NO_EVIDENCE = "NO_EVIDENCE"
    INCONCLUSIVE = "INCONCLUSIVE"
    NONE = "NONE"  # job not yet in a terminal research state
```

`derive_research_outcome(job_status, evidence, sealed=None) -> ResearchOutcome`:

| Inputs | Result |
| --- | --- |
| `sealed` is `FOUND` and evidence still complete | `FOUND` (already sealed; cancel/fail cannot unseal) |
| `FAILED` or `CANCELLED` and no sealed `FOUND` | `INCONCLUSIVE` |
| `COMPLETED` and any required gate missing/corrupt | `INCONCLUSIVE` |
| `COMPLETED` and every required gate present and all pass | `FOUND` |
| `COMPLETED` and every required gate present and any fail | `NO_EVIDENCE` |
| `QUEUED` or `RUNNING` | `NONE` |

Timeout or budget exhaustion with an incomplete evidence set is
`COMPLETED` + `INCONCLUSIVE`, not `NO_EVIDENCE`.

### 3.2 Frozen research spec

```python
@dataclass(frozen=True)
class Hypothesis:
    statement: str
    economic_logic: str
    signal_mechanism: str
    market_scope: str          # asset universe description
    market_profile: str        # "us-equity-daily" | "crypto-daily"
    benchmark: str

@dataclass(frozen=True)
class SuccessCriteria:
    hard_gates: tuple[str, ...]  # HardGateName values, frozen at start

@dataclass(frozen=True)
class ResearchSpec:
    spec_id: str
    hypothesis: Hypothesis
    success_criteria: SuccessCriteria
    seed: int
    time_budget_s: int
    cost_budget_usd: float
```

A run may append methodological revisions to `trial-ledger.jsonl`. It
must not mutate `ResearchSpec.hypothesis` or
`ResearchSpec.success_criteria`. Changing `signal_mechanism`,
`market_scope`, `benchmark`, or the hard-gate set requires a new spec
and a new run.

### 3.3 Hard gates

Phase 1 wraps the existing diagnostic functions. Required names:

```python
class HardGateName(str, Enum):
    DSR = "dsr"
    WALK_FORWARD = "walk_forward"
    VS_RANDOM = "vs_random"
    VS_BUY_HOLD = "vs_buy_hold"
    VS_BENCHMARK = "vs_benchmark"      # SPY for us-equity-daily
    DATA_CONSISTENCY = "data_consistency"
```

`llm_judge` is **not** a `HardGateName`.

```python
@dataclass(frozen=True)
class GateResult:
    name: HardGateName
    passed: bool
    detail: dict

@dataclass(frozen=True)
class GateEvidence:
    results: tuple[GateResult, ...]
    required: tuple[HardGateName, ...]
```

`evaluate_hard_gates(required, results) -> GateEvidence` raises
`IncompleteEvidenceError` if any required name is missing. Callers must
translate that into `INCONCLUSIVE`, never `FOUND`.

### 3.4 Artifact layout

```text
runs/<run_id>/
├── research-spec.yaml
├── manifest.yaml
├── trial-ledger.jsonl
├── checkpoints/
├── candidates.parquet
├── evidence/
├── recommendations.json
└── report.md
```

`RunLayout(run_dir: Path)` exposes those paths. Dataset bytes live in a
shared cache keyed by content hash; `manifest.yaml` stores
`dataset_id` and `dataset_sha256`. Replay must fail if the hash
mismatches or the bytes are missing.

v0.7 files (`top5.json`, `results.parquet`) may continue to be written
during the compatibility window. They are views, not the source of
truth, once `evidence/` exists.

### 3.5 Strategy Candidate Bundle

```python
@dataclass(frozen=True)
class StrategyCandidateBundle:
    schema_version: str
    bundle_id: str              # content-addressed, derived from canonical hash
    content_hash: str
    strategy_dsl: dict
    market_profile: str
    parameters: dict
    risk_envelope: dict
    lineage: dict
    conformance: dict           # fixed inputs + expected {asset_id: weight}
    registry_uri: str | None    # optional; first release must allow None
```

Canonicalization: JSON with sorted keys, UTF-8, no secrets, no
executable blobs. `bundle_id = "b_" + content_hash[:32]`. Unknown
payload keys are rejected. The hashed document is YAML/DSL data only;
`.py` source is not a bundle field and must not appear in the `.asb`
archive.

`alphaloop.strategies` Python classes are the in-repo interpreter
backend for named DSL `kind`s. They stay in this repository. They are
not serialized into the candidate bundle. AlphaStrategy runs a bundle
by loading the YAML with a versioned DSL interpreter that produces
`effective_at -> {asset_id: target_weight}` and must pass the bundled
conformance fixtures. Handoff convenience is that interpreter import,
not a per-candidate Python file.

Export is allowed only when `ResearchOutcome == FOUND` and the
candidate id is in the sealed evidence. The CLI command is
`alphaloop export <candidate_id> --output strategy.asb`.

DSL output semantics for later phases:

```text
effective_at -> {asset_id: target_weight}
```

AlphaStrategy maps weights to orders. alphaloop never emits broker
orders.

## 4. How existing modules are reused

### 4.1 Diagnostics

Phase 3's protocol calls the current functions:

- `deflated_sharpe`
- `walk_forward_cv`
- `vs_random`
- `vs_buy_hold`
- `vs_spy_buyhold` (US equity profile; crypto profile supplies its own
  benchmark adapter with the same `GateResult` shape)
- `data_source_consistency`

`loop/aggregator.py:diagnose_task` must stop synthesizing Sharpes. Until
Phase 3 lands, Phase 1 tests lock the contract so a later swap cannot
let `passes_all` imply `FOUND` without `GateEvidence`.

### 4.2 Strategies and signals

`strategies.base.Signal` already has `weight`. The DSL compiler will
emit target-weight series and ignore `action` as the execution contract.
Do not add an order object to `Signal`.

The planner must emit DSL documents, not `MovingAverageCrossoverStrategy`
class names. Until the DSL exists, Phase 1 forbids bundle export of
class-name candidates. Precise control that the current DSL cannot
express is a DSL extension (or a preflight rejection), not a `.py`
file in the bundle.

### 4.3 LoopRunner compatibility

Keep `LoopRunner` callable in Phase 1–2 so current tests pass. Mark it
as compatibility:

- It must not import `contracts.bundle`.
- Phase 2 Job API may shell `LoopRunner` inside a worker **only** as a
  stopgap, and must still persist `JobStatus` separately from any
  termination letter.
- Phase 3 replaces `LoopRunner.run` control flow with `protocol.loop`.

### 4.4 live/

Remove `AlpacaAdapter` and related names from `alphaloop.__init__.__all__`.
Keep the package and its tests. Add a guard test:
`alphaloop.runtime` and `alphaloop.protocol` module files contain no
`alphaloop.live` import.

## 5. Later phases (design only; separate plans)

### Phase 2 — Durable local runtime

Implementation plan:
[`docs/plans/2026-08-19-overnight-lab-phase2-runtime.md`](2026-08-19-overnight-lab-phase2-runtime.md).

- `alphaloop start` launches a local daemon (Job API + static web root).
- `create_run` returns `run_id` immediately.
- Supervisor heartbeats and restarts workers from checkpoints.
- Browser/CLI exit does not stop the job; host sleep/power-off does,
  and preflight must disclose that.

### Phase 3 — Research protocol

Implementation plan:
[`docs/plans/2026-08-19-overnight-lab-phase3-protocol.md`](2026-08-19-overnight-lab-phase3-protocol.md).

- Constrained DSL over `engineer` + `strategies`.
- Epistemic stop: method repairs allowed; economic-logic changes queued.
- Independent `us-equity-daily` and `crypto-daily` profiles.
- Wire real diagnostics into `evaluate_hard_gates`.

### Phase 4 — Morning Web

Implementation plan:
[`docs/plans/2026-08-19-overnight-lab-phase4-morning-web.md`](2026-08-19-overnight-lab-phase4-morning-web.md).

- Packaged static UI, no Node on the user PATH.
- Home page leads with `FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE`.
- Cannot override gates.

### Phase 5 — `.asb` producer

Implementation plan:
[`docs/plans/2026-08-19-overnight-lab-phase5-asb.md`](2026-08-19-overnight-lab-phase5-asb.md).

- Implement archive format using Phase 1 `StrategyCandidateBundle`.
- Shared conformance fixtures for a future AlphaStrategy consumer.
- No reverse telemetry.

### Phase 6 — Agent Skill

Implementation plan:
[`docs/plans/2026-08-19-overnight-lab-phase6-skill.md`](2026-08-19-overnight-lab-phase6-skill.md).

- Local Skill + CLI: preflight, submit, poll, interpret outcomes.
- No overnight MCP tool call.

### Phase 7 — Iterative protocol loop

Implementation plan:
[`docs/plans/2026-08-19-overnight-lab-phase7-iterative-protocol.md`](2026-08-19-overnight-lab-phase7-iterative-protocol.md).

- Honor `should_continue` inside `run_protocol` (do not discard the decision).
- Method-repair parameter search with `n_trials` equal to the trial-ledger length.
- Queue economic revisions into `recommendations.json`; never execute them in the same run.
- Stop on `FOUND`, complete hard-gate failure, forbidden continue reasons, or exhausted budget.

Phases 8–11 shipped. The remaining-work design is historical:
[`docs/plans/2026-08-19-overnight-lab-remaining-work.md`](2026-08-19-overnight-lab-remaining-work.md).

### Phase 8 — Protocol semantics

Implementation plan:
[`docs/plans/2026-08-19-overnight-lab-phase8-protocol-semantics.md`](2026-08-19-overnight-lab-phase8-protocol-semantics.md).

- Hard gates see lagged target-weight returns for the current grid trial.
- Complete passing evidence is `FOUND` even if the clock expires during that trial.
- Production worker passes a monotonic clock and the spec cost budget.

### Phase 9 — Durability and artifacts

Implementation plan:
[`docs/plans/2026-08-19-overnight-lab-phase9-durability-artifacts.md`](2026-08-19-overnight-lab-phase9-durability-artifacts.md).

- Content-addressed dataset fail-closed; no synthetic prices in the worker.
- Resume skips checkpointed `trial_id`s; `n_trials` follows unique ledger ids.
- Write `manifest.yaml`, `candidates.parquet`, `report.md`; `alphaloop replay` re-emits the report.

### Phase 10 — Morning submit and progress

Implementation plan:
[`docs/plans/2026-08-19-overnight-lab-phase10-morning-submit.md`](2026-08-19-overnight-lab-phase10-morning-submit.md).

- YAML textarea POST to `/v1/jobs` without a precomputed `spec_id`.
- Show preflight errors and host constraint; poll job list. No gate override.

### Phase 11 — Verification

Implementation plan:
[`docs/plans/2026-08-19-overnight-lab-phase11-verification.md`](2026-08-19-overnight-lab-phase11-verification.md).

- CI pytest excluding integration/LLM. Shortened overnight e2e. Checkpoint resume uniqueness.
- Soak and five-minute review stay a release checklist, not CI.

## 6. Public API and CLI after Phase 1

`alphaloop.__init__` documents the overnight lab, exports core research
types plus diagnostics, and does **not** export live trading names.

CLI after Phase 1:

- existing: `backtest`, `optimize`, `fetch`, `report`, `loop`, `judge`
- new: `export` (refuses unless outcome is `FOUND`)

`start` waits for Phase 2.

## 7. Testing strategy for the refactor

- Contract tests own the enums, derivation table, hash stability, and
  export guard.
- Existing diagnostic and engineer tests remain green; do not weaken
  them.
- A packaging test imports `alphaloop.cli.main:main` and asserts
  `pyproject.toml` scripts/entry match.
- Negative tests: missing gate, mutated spec, LLM-judge-only pass, and
  non-FOUND export.
- Import-graph test: `runtime`/`protocol`/`contracts` do not import
  `live`.

## 8. Non-goals of this refactor

- Official cloud, remote workers, registry, desktop app, MCP runtime.
- AlphaStrategy execution implementation.
- Rewriting `diagnostic`, `engineer`, `data`, or `backtest` math.
- Expanding `live/` beyond its current read-only hard wall.
