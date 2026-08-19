---
title: "alphaloop v0.7 — Hybrid Loop MVP Design"
version: "0.7"
status: "design"
authors:
  - alphaloop design subagent (Coder)
date: "2026-08-14"
loop: "alphaloop-v07-hybrid-loop-design"
related_roadmap_section: "ROADMAP.md § v0.7"
supersedes: "ROADMAP.md § v0.7 (high-level intent only — this doc is the full design)"
---

# alphaloop v0.7 — Hybrid Loop MVP Design

## 0. Context

alphaloop v0.6 (commit `93e7b5a` on `AlphaStrategyAI/alphaloop`) ships an
**LLM-as-judge** evaluator that scores backtest reports on three narrative
dimensions (readability, decision合理性, risk-disclosure completeness).
The v0.5 diagnostic core ships 6 deterministic checks (DSR, walk-forward
CV, cross-source consistency, vs-random, vs-buy-hold, vs-SPY).

Per **ROADMAP.md § v0.7** and **Jeff Dean's point #8 ("AI builds AI")**,
v0.7 wires the existing components into an **end-to-end autonomous
research loop**: one CLI command loads data, plans a search space,
executes parallel backtests, runs the 6 diagnostics + the LLM judge,
ranks the results, and writes a reproducible artifact set.

**v0.7 does not invent new diagnostics.** It composes the v0.5 + v0.6
primitives into a DAG, adds a planner, adds persistence, and adds a
deterministic runtime that makes a single ~6-hour run fully
reproducible.

This document is the **design only** — no implementation. It defines the
5 sections the user requested: **Goals**, **Architecture**, **API**,
**Tests**, **Risks**. Per the loop state file, implementation is gated
on user explicit OK after this design is reviewed.

---

## 1. Goals

### 1.1 Primary goal

Ship a `loop` subcommand such that

```bash
alphaloop loop "find a strategy that beats SPY with DSR > 1.0"
```

runs end-to-end for ≤ 6 hours on a single multi-core workstation, then
returns a **reproducible top-5 strategy report** (Markdown + JSON +
Parquet) committed to a local `runs/<run_id>/` directory.

### 1.2 User-confirmed decisions (frozen)

The 5 design decisions the user already approved are baked in below
and **not** open for renegotiation in this doc:

| # | Decision | Choice |
|---|----------|--------|
| 1 | Orchestration | **Hybrid (DAG + Plan)** — static 6-node skeleton, LLM plans inside each planner node |
| 2 | Parallelism | **`multiprocessing.Pool(N=cpu_count)` for backtests** + `asyncio` main loop |
| 3 | Persistence | **Mixed** — `manifest.yaml` + `results.parquet` + `top5.json` + `report.md` per run |
| 4 | Reproducibility | **A+B+C+D all** — random seed + data snapshot + git commit + `run_id` |
| 5 | Termination | `(A) target found` **OR** `(B) all tasks done` **OR** `(C) 6h timeout` **OR** `(D) $5 cost` |

### 1.3 Why "hybrid" and not pure-DAG or pure-plan

- **Pure DAG** (e.g. Airflow, Prefect) gives reproducibility but forces
  every decision into the static graph — LLM planner decisions would
  have to be encoded as parameters on DAG nodes. That's the wrong
  abstraction for "which 500 strategy×factor×parameter combos to run".
- **Pure plan** (e.g. AutoGPT, an LLM agent that picks every step)
  gives flexibility but reproducibility is destroyed: the LLM might
  pick different branches on the next run. That's incompatible with
  decision (4) "all of A+B+C+D".
- **Hybrid** gives both: the *skeleton* (which 6 stages run in which
  order) is static and deterministic; *inside* the planner nodes
  (N1, N2, N5) the LLM gets freedom, but its output is **snapshotted
  into the manifest** so the next run can replay the same plan.

This is the same pattern used by Sakana AI's "AI Scientist" and parts
of Google's AlphaEvolve — fixed scaffolding + LLM in the planning
slots, deterministic execution elsewhere.

### 1.4 Why `multiprocessing.Pool` (not `ProcessPoolExecutor` / `asyncio`)

The compute-heavy stage (N3) is **CPU-bound** vectorized NumPy work,
**not** I/O-bound. `multiprocessing.Pool` has three properties that
matter here:

1. **Process isolation** — a buggy backtest can't crash the main
   orchestrator. (Sharing memory with `ProcessPoolExecutor` is more
   error-prone.)
2. **Predictable CPU pinning** — `Pool(processes=cpu_count)` reserves
   the whole machine for the compute stage; the async main loop yields
   to it and doesn't fight for cores.
3. **Pickle-clean task boundary** — strategies and data are simple
   dataclasses, already picklable for `Engine.run(backtest_id)`. We
   don't need a fancy serialization layer.

`asyncio` runs the **main loop** (N1, N2, N4, N5, N6) because those
stages are I/O-heavy (LLM HTTP calls, file writes, git ops) and benefit
from cooperative scheduling without threads.

### 1.5 Non-goals (explicitly out of scope for v0.7)

- **Live trading.** N6 commits reports to git. It does **not** talk
  to a broker. (`live/alpaca.py` stays untouched.)
- **Multi-agent meta-eval.** Running multiple `loop` instances and
  picking the best is v2.0, not v0.7.
- **Self-feedback / auto-redesign.** If N5 sees a failed plan, it
  does **not** re-invoke N2 with a revised prompt. One-shot loop.
- **New diagnostics.** v0.7 composes existing 6 + judge. It does not
  add an 8th check.
- **Distributed compute.** Single machine, multi-core. Ray / Dask /
  Kubernetes are deferred.
- **Online learning.** All data is snapshot-loaded before N2 plans.
  No incremental updates during N3.

### 1.6 Success criteria (measurable)

The design is successful if, after implementation, all of the following hold:

- `alphaloop loop "<goal>"` runs end-to-end on a fresh checkout,
  creates `runs/<run_id>/`, and exits 0 within ≤ 6h.
- The run produces all 4 persistence artifacts (`manifest.yaml`,
  `results.parquet`, `top5.json`, `report.md`) and they parse cleanly.
- `alphaloop loop replay --run-id <id>` reproduces the same `top5.json`
  byte-for-byte given the same data snapshot and `LLM_MODEL`.
- A 95% confidence interval on DSR for each top-5 entry is reported in
  the Markdown.
- Total cost (LLM API + compute) ≤ $5 per run for a budget-tier
  model (e.g. GPT-4o-mini, Claude Haiku, local vLLM).
- Test suite grows from v0.6's 206 → ≥ 240 (≥ 34 new tests covering
  the 6 nodes, persistence, replay, and termination gates).
- A `runs/<run_id>/commit.txt` file contains the exact `git rev-parse
  HEAD` so a reviewer can `git checkout` that commit and re-run
  replay.

---

## 2. Architecture

### 2.1 The 6-node hybrid DAG

```
                          ┌──────────────────────┐
                          │  N1  Load Data       │  ← LLM plan
                          │   (LLM planner)      │
                          └──────────┬───────────┘
                                     │ snapshot
                                     ▼
                          ┌──────────────────────┐
                          │  N2  Plan Strategies │  ← LLM plan
                          │   (LLM planner)      │
                          └──────────┬───────────┘
                                     │ N task specs
                                     ▼
                          ┌──────────────────────┐
                          │  N3  Execute Backtst │  ← NO LLM
                          │   (multiprocessing)  │
                          └──────────┬───────────┘
                                     │ results
                                     ▼
                          ┌──────────────────────┐
                          │  N4  Diagnose        │  ← 7 diags incl.
                          │   (LLM judge per Q7) │     v0.6 judge
                          └──────────┬───────────┘
                                     │ scored rows
                                     ▼
                          ┌──────────────────────┐
                          │  N5  Aggregate       │  ← LLM writes
                          │   (LLM report)       │     report.md
                          └──────────┬───────────┘
                                     │ top5 + report.md
                                     ▼
                          ┌──────────────────────┐
                          │  N6  Commit          │  ← NO LLM
                          │   (git + manifest)    │
                          └──────────────────────┘
```

| Node | LLM? | Wall budget | Output |
|------|------|-------------|--------|
| N1 Load Data | Yes (plan) | ≤ 60 s | `data_snapshot.pkl`, `data_manifest.json` |
| N2 Plan Strategies | Yes (plan) | ≤ 120 s | `task_specs.parquet` (~500 rows) |
| N3 Execute Backtests | **No** | ≤ 5 h | `results.parquet` (1 row/task + raw metrics) |
| N4 Diagnose | Mixed (Q1–Q6 deterministic; Q7 = LLM judge) | ≤ 50 min | `diagnostics.parquet` (7 cols + per-task) |
| N5 Aggregate | Yes (write report.md) | ≤ 30 s | `top5.json`, `report.md` |
| N6 Commit | No | ≤ 30 s | `runs/<id>/commit.txt`, git commit |

Total wall budget: ≤ 6 h, dominated by N3 (parallel CPU) and N4 (Q7
LLM judge fan-out over ~500 tasks).

### 2.2 Module layout (proposed)

```
src/alphaloop/
├── loop/                       # NEW PACKAGE (v0.7)
│   ├── __init__.py
│   ├── runner.py               # LoopRunner class — orchestrator
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── n1_load_data.py
│   │   ├── n2_plan.py
│   │   ├── n3_execute.py
│   │   ├── n4_diagnose.py
│   │   ├── n5_aggregate.py
│   │   └── n6_commit.py
│   ├── planner.py              # shared LLM planner helper
│   ├── executor.py             # multiprocessing.Pool wrapper
│   ├── persistence.py          # manifest.yaml + parquet writer
│   ├── termination.py          # 4 gates (A/B/C/D) — see § 2.7
│   ├── replay.py               # LoopReplay class
│   └── schemas.py              # RunManifest, TaskSpec, RunResult dataclasses
├── cli/
│   └── loop.py                 # NEW — `alphaloop loop` subcommand
└── judge/                      # unchanged (v0.6)
```

The split mirrors v0.6's `diagnostic/` + `judge/` pattern: pure public
API in `loop/` (dataclasses + thin functions), infrastructure
(multiprocessing, git, parquet) inside `loop/` submodules. Tests can
inject fakes the same way `FakeLLMClient` did in v0.6.

### 2.3 Data flow at runtime

```
   $ alphaloop loop "find alpha with DSR > 1.0"
        │
        ▼
   ┌────────────────────────────────────────────────────────────┐
   │  LoopRunner.run(goal, run_id=None)                         │
   │   1. allocate runs/<run_id>/                               │
   │   2. seed random; write manifest.yaml header               │
   │   3. async def step_n1(): planner → snapshot data         │
   │   4. async def step_n2(): planner → 500 task specs        │
   │   5. await step_n3(): Pool.imap_unordered → results       │
   │   6. await step_n4(): per-task diagnostics + Q7 judge     │
   │   7. async def step_n5(): LLM writes report.md            │
   │   8. step_n6(): git commit + write commit.txt             │
   │   9. emit LoopSummary to stdout                            │
   └────────────────────────────────────────────────────────────┘
        │
        ▼
   runs/2026-08-14T12-34-56Z_a1b2c3/
   ├── manifest.yaml
   ├── data_snapshot.pkl
   ├── data_manifest.json
   ├── task_specs.parquet
   ├── results.parquet
   ├── diagnostics.parquet
   ├── top5.json
   ├── report.md
   ├── judge_calls/             # raw Q7 LLM I/O for replay
   │   ├── 0001.json
   │   └── ...
   ├── commit.txt
   └── replay.sh                # exact command to reproduce
```

### 2.4 Relationship to v0.5 + v0.6

v0.7 is a thin orchestration layer. It **imports** but does **not
modify**:

- `src/alphaloop/data/*` (4 sources) — N1 reads them
- `src/alphaloop/strategies/*` (11 strategies) — N3 runs them
- `src/alphaloop/diagnostic/*` (6 base + 1 judge) — N4 calls them
- `src/alphaloop/engineer/*` (factors) — N2 may sample from them
- `src/alphaloop/backtest/engine.py` — N3's worker function
- `src/alphaloop/judge/client.py` — N4 Q7's HTTP layer

No file outside `src/alphaloop/loop/` and `src/alphaloop/cli/loop.py`
is modified. v0.5 + v0.6 tests remain green (191 + 15 = 206).

### 2.5 Asyncio ↔ multiprocessing bridge

The orchestrator runs in `asyncio` (cooperative, single-thread for
N1/N2/N4/N5/N6). When N3 fires:

```python
async def step_n3(self) -> list[BacktestResult]:
    loop = asyncio.get_running_loop()
    with multiprocessing.Pool(processes=cpu_count()) as pool:
        # imap_unordered yields as results arrive; offload to thread
        # so the event loop stays responsive to SIGINT/Ctrl-C
        async for result in _aiter_pool(pool.imap_unordered(
                _run_one_backtest, self._task_specs, chunksize=4)):
            self._check_termination_gates()  # polls D (cost) gate
            yield result
            await asyncio.sleep(0)            # yield to event loop
```

`_aiter_pool` is a small adapter (~15 lines) that wraps the blocking
`imap_unordered` iterator in an async generator. The event loop wakes
every `chunksize=4` results (~few seconds at typical backtest cost)
to check the cost gate and to honor Ctrl-C cleanly.

### 2.6 Persistence: the 4 artifacts

| File | Format | Producer | Consumer |
|------|--------|----------|----------|
| `manifest.yaml` | YAML | N1 start | Replay, audit |
| `results.parquet` | Parquet (snappy) | N3 | N4, N5, replay |
| `top5.json` | JSON | N5 | UI, replay, downstream |
| `report.md` | Markdown | N5 | Human reviewer |

`manifest.yaml` is the source of truth for *what was attempted*: run
id, goal text, `git rev-parse HEAD`, LLM_MODEL used, data snapshot
hash, list of task ids, termination reason. **No PII, no secrets** —
the API key is *never* written (resolved at runtime, never persisted).

`results.parquet` schema (one row per task):

| column | type | description |
|--------|------|-------------|
| `task_id` | str | uuid4 |
| `strategy` | str | strategy class name |
| `factor` | str | factor class name |
| `params` | str | JSON-serialized param dict |
| `dsr` | float | Deflated Sharpe Ratio |
| `sharpe` | float | raw Sharpe |
| `cagr` | float | annualized return |
| `max_dd` | float | max drawdown |
| `turnover` | float | annual turnover |
| `diagnostics` | str | JSON of {Q1–Q7 results} |
| `latency_s` | float | wall time for backtest |

### 2.7 The 4 termination gates

```python
def should_terminate(state: RunState) -> Optional[str]:
    """Return None if continuing, else a reason string."""
    # Gate A — target found
    if any(r.dsr > state.target_dsr for r in state.scored):
        return "A: target_dsr_achieved"

    # Gate B — all tasks done
    if state.completed_tasks == state.total_tasks:
        return "B: tasks_complete"

    # Gate C — wall clock
    if state.elapsed_s() > 6 * 3600:
        return "C: timeout_6h"

    # Gate D — cost
    if state.estimated_cost_usd() > 5.0:
        return "D: cost_cap_5usd"

    return None
```

Gates are checked:
- **A & B** — after every N3 result & after every N4 batch.
- **C** — every 30 s from a background task.
- **D** — every N4 Q7 judge call (cost is dominated by Q7).

The `termination_reason` is recorded in `manifest.yaml` and in the
final `LoopSummary` so the user knows why the loop stopped.

### 2.8 Reproducibility: A+B+C+D

| Layer | Implementation |
|------|----------------|
| **A. Random seed** | `random.seed(seed)` + `numpy.random.seed(seed)` + `torch.manual_seed(seed)` at N1 start; seed written to manifest |
| **B. Data snapshot** | N1 writes `data_snapshot.pkl` (a frozen `pd.DataFrame` per symbol); replay reads from this file, **not** from APIs |
| **C. Git commit** | N6 captures `git rev-parse HEAD` into `commit.txt`; replay runs from that commit |
| **D. Run id** | `run_id = "<ISO8601-utc>_<sha8-of-(goal+seed+model)>"`, written everywhere |

Together: given `run_id` + the same data snapshot + the same `LLM_MODEL`
+ the same alphaloop git commit, **`alphaloop loop replay --run-id X`
must reproduce `top5.json` byte-for-byte**.

Note: LLM outputs are **not** deterministic across runs even with seed=0
unless the model supports it. The replay contract is therefore
"`results.parquet` (deterministic) + `top5.json` *deterministic given
the same judge_calls/* files*". This is honest: we record the raw
Q7 I/O under `judge_calls/`, and replay consumes them, so the
planner-driven parts (N1, N2, N5) and the Q7 calls are all replayable.

### 2.9 Configuration resolution order

All LLM-related env vars follow v0.6's pattern:

| Variable | Purpose | Default |
|----------|---------|---------|
| `LLM_API_KEY` | Bearer token | required (else Q7 SKIP) |
| `LLM_BASE_URL` | OpenAI-compatible URL | no default — user picks |
| `LLM_MODEL` | Model name | no default — user picks |
| `LOOP_BUDGET_USD` | Hard cost cap for gate D | `5.0` |
| `LOOP_TIMEOUT_S` | Wall-clock cap for gate C | `21600` (6h) |
| `LOOP_TARGET_DSR` | DSR threshold for gate A | `1.0` |
| `LOOP_SEED` | Random seed (gate A.1) | random if unset |
| `LOOP_DATA_DIR` | Where to write `runs/` | `./runs` |

Loop also accepts CLI flags `--budget`, `--timeout`, `--target-dsr`,
`--seed`, `--model` — each overrides the env var for that invocation.

---

## 3. API

### 3.1 Public Python API

```python
# src/alphaloop/loop/schemas.py

from dataclasses import dataclass, field
from typing import Optional, Literal
import uuid


@dataclass
class TaskSpec:
    """One row in task_specs.parquet."""
    task_id: str                       # uuid4 hex
    strategy: str                      # e.g. "MovingAverageCross"
    factor: str                        # e.g. "Momentum12M"
    params: dict                       # strategy-specific params
    data_snapshot_hash: str            # sha256 of the data slice


@dataclass
class BacktestResult:
    """Output of one N3 worker."""
    task_id: str
    metrics: dict                      # sharpe, cagr, max_dd, turnover, ...
    latency_s: float
    error: Optional[str] = None        # populated iff backtest raised


@dataclass
class ScoredResult:
    """Output of N4: backtest + 7 diagnostics."""
    task_id: str
    backtest: BacktestResult
    dsr: float                         # Q1
    cv: dict                           # Q2 walk-forward result
    consistency: dict                  # Q3
    vs_random: dict                    # Q4
    vs_buyhold: dict                   # Q5
    vs_spy: dict                       # Q6
    judge: Optional[dict]              # Q7 (None if SKIP)
    passes_all: bool                   # all 7 booleans AND


@dataclass
class RunManifest:
    """Header of manifest.yaml."""
    run_id: str
    goal: str
    seed: int
    git_commit: str
    llm_model: str                     # actual, not requested
    data_snapshot_path: str
    data_snapshot_sha256: str
    target_dsr: float
    budget_usd: float
    timeout_s: int
    started_at: str                    # ISO8601 UTC
    finished_at: Optional[str] = None
    termination_reason: Optional[Literal["A","B","C","D"]] = None
    estimated_cost_usd: float = 0.0
    task_count: int = 0


@dataclass
class TopPick:
    rank: int                          # 1..5
    task_id: str
    strategy: str
    factor: str
    params: dict
    dsr: float
    sharpe: float
    cagr: float
    max_dd: float
    passes_all: bool
    one_line_thesis: str               # from report.md
```

### 3.2 `LoopRunner` class

```python
# src/alphaloop/loop/runner.py

class LoopRunner:
    """The orchestrator. One instance per `alphaloop loop` invocation."""

    def __init__(
        self,
        goal: str,
        *,
        run_id: Optional[str] = None,
        seed: Optional[int] = None,
        budget_usd: float = 5.0,
        timeout_s: int = 6 * 3600,
        target_dsr: float = 1.0,
        data_dir: str = "./runs",
        llm_client: Optional[LLMClient] = None,   # DI for tests
        backtest_fn: Optional[Callable] = None,   # DI for tests
    ) -> None:
        ...

    async def run(self) -> RunSummary:
        """Execute the full 6-node DAG; return a summary."""
        ...

    async def cancel(self, reason: str) -> None:
        """Soft-cancel: stop after current N3 batch, write manifest, return."""
        ...


@dataclass
class RunSummary:
    run_id: str
    termination_reason: str            # "A" / "B" / "C" / "D"
    elapsed_s: float
    estimated_cost_usd: float
    completed_tasks: int
    total_tasks: int
    top5: list[TopPick]
    artifacts_dir: str
```

### 3.3 `LoopReplay` class

```python
# src/alphaloop/loop/replay.py

class LoopReplay:
    """Re-run a previous loop deterministically from its artifacts."""

    def __init__(self, run_id: str, *, data_dir: str = "./runs") -> None:
        ...

    async def run(self) -> RunSummary:
        """Re-execute N3 + N4 (deterministic parts) and re-derive top5.

        Uses `judge_calls/*` if present (no LLM HTTP calls).
        """
        ...
```

### 3.4 CLI surface

```bash
alphaloop loop "<goal>" [--run-id ID] [--seed N]
                       [--budget USD] [--timeout S]
                       [--target-dsr F] [--model NAME]
                       [--data-dir DIR] [--dry-run]

alphaloop loop replay --run-id ID [--data-dir DIR]

alphaloop loop inspect --run-id ID    # print manifest + top5 summary
alphaloop loop list                   # list all runs in --data-dir
```

Flag names follow v0.6's pattern (`--judge-model`, `--seed`,
`--method`). `--dry-run` runs N1+N2 only and prints the planned task
list without executing N3–N6 — useful for budget estimation before
committing $5.

### 3.5 `manifest.yaml` schema

```yaml
# runs/2026-08-14T12-34-56Z_a1b2c3d4/manifest.yaml
run_id: "2026-08-14T12-34-56Z_a1b2c3d4"
goal: "find a strategy that beats SPY with DSR > 1.0"
seed: 42
git_commit: "93e7b5a4f1..."
llm_model: "gpt-4o-mini"          # actual, not requested
data_snapshot_path: "data_snapshot.pkl"
data_snapshot_sha256: "9f2e..."
target_dsr: 1.0
budget_usd: 5.0
timeout_s: 21600
started_at: "2026-08-14T12:34:56Z"
finished_at: "2026-08-14T17:51:02Z"
termination_reason: "B"
estimated_cost_usd: 1.23
task_count: 500
```

YAML is human-editable so a reviewer can tweak `target_dsr`,
`budget_usd`, or `timeout_s` and re-run replay without code changes.

### 3.6 `top5.json` schema

```json
{
  "run_id": "2026-08-14T12-34-56Z_a1b2c3d4",
  "termination_reason": "B",
  "top5": [
    {
      "rank": 1,
      "task_id": "a3f4...",
      "strategy": "MovingAverageCross",
      "factor": "Momentum12M",
      "params": {"fast": 20, "slow": 100},
      "dsr": 1.42,
      "sharpe": 0.91,
      "cagr": 0.124,
      "max_dd": -0.183,
      "passes_all": true,
      "one_line_thesis": "20/100 MA cross on SPY + 12M momentum filter..."
    },
    ...
  ]
}
```

JSON is the machine-readable contract for downstream tools (v1.0
MCP server, OpenRouter Fusion, future v2.0 meta-evaluator).

### 3.7 No broker API in v0.7

Explicit per the loop state file hard wall: `alphaloop loop` does not
import `src/alphaloop/live/*`. N6 commits the *report*, not a *trade*.
This is enforced by a CI lint rule:

```python
# tests/test_loop/test_no_broker_import.py
def test_loop_does_not_import_live_modules():
    """Hard wall: v0.7 must not touch live/broker."""
    for path in pathlib.Path("src/alphaloop/loop").rglob("*.py"):
        src = path.read_text()
        assert "from alphaloop.live" not in src
        assert "import alphaloop.live" not in src
```

---

## 4. Tests

### 4.1 Test layout

```
tests/
├── loop/                            # NEW
│   ├── __init__.py
│   ├── conftest.py                  # FakeLLMClient, FakeBacktestFn
│   ├── test_runner.py               # 6-node orchestration
│   ├── test_n1_load_data.py
│   ├── test_n2_plan.py
│   ├── test_n3_execute.py           # multiprocessing semantics
│   ├── test_n4_diagnose.py
│   ├── test_n5_aggregate.py
│   ├── test_n6_commit.py
│   ├── test_termination.py          # 4 gates A/B/C/D
│   ├── test_persistence.py          # manifest + parquet + JSON round-trip
│   ├── test_replay.py               # golden-file determinism
│   └── test_no_broker_import.py     # hard-wall CI lint
```

Target: **34 new tests** (≥ 30 unit + 4 integration), bringing the
total to 206 + 34 = **240 passing**.

### 4.2 Mock infrastructure (conftest.py)

Three fakes — same pattern as v0.6's `FakeLLMClient`:

```python
@dataclass
class FakeLLMClient:
    """Records calls, returns scripted responses."""
    responses: list[str] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    _idx: int = 0
    def complete(self, messages, model, **_): ...

@dataclass
class FakeBacktestFn:
    """Returns deterministic fake BacktestResult per task_id."""
    latencies: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, dict] = field(default_factory=dict)
    def __call__(self, spec: TaskSpec) -> BacktestResult: ...

@dataclass
class FakeClock:
    """Controls wall-clock for termination gate C."""
    now_s: float = 0.0
    def advance(self, dt_s: float) -> None: ...
```

### 4.3 Unit tests per node (24 tests)

| # | Node | Test name | Asserts |
|---|------|-----------|---------|
| 1 | N1 | `test_n1_writes_data_snapshot` | `data_snapshot.pkl` exists, sha256 in manifest |
| 2 | N1 | `test_n1_uses_llm_to_pick_sources` | LLM called with goal in user message |
| 3 | N1 | `test_n1_skips_llm_if_goal_has_data_hint` | regex match → no LLM call |
| 4 | N2 | `test_n2_generates_500_tasks` | `len(task_specs.parquet) == 500` |
| 5 | N2 | `test_n2_respects_strategy_universe` | every task's strategy ∈ 11 known |
| 6 | N2 | `test_n2_persists_prompt_and_response` | `n2_llm_io.json` written |
| 7 | N3 | `test_n3_uses_all_cores` | `len(pool._processes) == cpu_count()` |
| 8 | N3 | `test_n3_results_have_one_row_per_task` | count matches task count |
| 9 | N3 | `test_n3_isolates_worker_failures` | one bad task → others still finish |
| 10 | N3 | `test_n3_writes_parquet_atomically` | tmp + rename, no half-written file |
| 11 | N4 | `test_n4_runs_all_7_diagnostics` | each row has 7 populated fields |
| 12 | N4 | `test_n4_q7_uses_v06_judge` | imports `diagnostic.judge.llm_judge` |
| 13 | N4 | `test_n4_q7_skipped_without_api_key` | SKIP rows in diagnostics.parquet |
| 14 | N4 | `test_n4_calls_terminate_after_each_batch` | gate checked ≥ once per batch |
| 15 | N5 | `test_n5_picks_top5_by_dsr` | top5.json sorted by dsr desc |
| 16 | N5 | `test_n5_excludes_non_passers` | `passes_all=False` rows filtered |
| 17 | N5 | `test_n5_writes_report_md_with_sections` | Q1–Q7 sections + summary |
| 18 | N5 | `test_n5_includes_one_line_thesis_per_pick` | 5 thesis strings present |
| 19 | N6 | `test_n6_writes_commit_txt` | `commit.txt` matches `git rev-parse HEAD` |
| 20 | N6 | `test_n6_does_not_push` | no `git push` ever invoked |
| 21 | N6 | `test_n6_records_termination_reason` | manifest.yaml updated |
| 22 | Term | `test_gate_a_target_found` | any DSR > target → terminate "A" |
| 23 | Term | `test_gate_b_all_tasks_done` | completed == total → "B" |
| 24 | Term | `test_gate_c_timeout` | elapsed > timeout → "C" |
| 25 | Term | `test_gate_d_cost` | estimated > budget → "D" |
| 26 | Persist | `test_manifest_yaml_round_trips` | `yaml.safe_load` → equal dict |
| 27 | Persist | `test_parquet_round_trip` | `pd.read_parquet` → equal DataFrame |
| 28 | Persist | `test_top5_json_schema` | jsonschema validates |
| 29 | Replay | `test_replay_no_llm_calls` | given judge_calls/, no HTTP |
| 30 | Replay | `test_replay_byte_equal_top5` | golden file compare |

### 4.4 Integration tests (4 tests)

| # | Test name | Asserts |
|---|-----------|---------|
| 31 | `test_loop_smoke_runs_with_synthetic_data` | end-to-end on 50-task synthetic universe, exits 0, all 4 artifacts present |
| 32 | `test_loop_dry_run_prints_plan_no_execution` | `--dry-run` writes N1+N2 only, no `results.parquet` |
| 33 | `test_loop_terminates_on_cost_with_injected_expensive_judge` | injected FakeLLMClient charging $100/call → gate D fires |
| 34 | `test_loop_handles_ctrl_c_gracefully` | SIGINT during N3 → manifest written, exit 130 |

### 4.5 Replay determinism (golden file)

The hardest test to write — and the most important:

```python
def test_replay_byte_equal_top5():
    """Given judge_calls/ + data_snapshot.pkl + git_commit,
    replay must produce identical top5.json."""
    run_dir = pathlib.Path("tests/fixtures/replay_golden/run_001")
    runner = LoopReplay(run_id="run_001", data_dir=run_dir.parent)
    summary = asyncio.run(runner.run())
    actual = json.dumps(summary.top5_dict, indent=2, sort_keys=True)
    expected = (run_dir / "top5.expected.json").read_text()
    assert actual == expected
```

The golden fixture is checked into git. CI fails if N3 ordering,
N4 tie-breaking, or N5 prompt changes drift the output.

### 4.6 Verification gate (per Coder Self-Harness)

```bash
cd /Users/assistant/hermes-lab/alphaloop && \
  python -m pytest tests/ -q --tb=short 2>&1 | tail -30
```

Expected: `240 passed in <time>`, exit code 0. Any failure → loop is
not done, return to fix.

---

## 5. Risks

### 5.1 Risk matrix

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | **LLM plan non-reproducibility** — N1/N2/N5 picks different branches across runs even with same seed | High | High | Every LLM call's request + response is snapshotted to `judge_calls/`. Replay consumes them instead of re-calling. The N3 backtest + N4 deterministic parts *are* reproducible. |
| R2 | **Multiprocessing pickling failure** — a strategy class instance is not picklable on macOS spawn | Medium | High | All N3 task inputs are pure dataclasses (`TaskSpec`); strategies are referenced by *name* string and re-imported in workers. Smoke-tested on macOS spawn + Linux fork. |
| R3 | **Cost overrun** — Q7 fan-out over 500 tasks × $0.01 = $5 easily blown | Medium | High | Gate D is checked every N4 batch. `LLM_TIMEOUT_S` defaults to 20s. Users can `--budget 1.0` for safety. `--dry-run` estimates cost before committing. |
| R4 | **6h timeout too tight** — N3 with 500 tasks × ~30s = ~4h on 8 cores, but slow CI runners blow past | Medium | Medium | `--timeout` flag overrides; gate C is a hard stop. Documented in `loop --help`. Users can pre-filter task count via `--max-tasks 100`. |
| R5 | **LLM judge hallucination of evidence quotes** (carried from v0.6 R6) | High | Medium | v0.6 unit test injects fake quote; v0.7 extends to per-task replay: bad quotes produce `passes_all=False` for the affected task, ranking falls back to numeric-only tasks. |
| R6 | **Node failure cascades** — N2 crashes → entire loop dead | Medium | High | Each node wraps its body in try/except; on caught exception, the node writes `nodes/<n>/error.json` and the runner re-raises. Manifest records `node_errors`. Tests cover N2 crash + recovery. |
| R7 | **Data snapshot staleness** — `data_snapshot.pkl` from 2024 Q1 used in 2026 replay | Low | Medium | Manifest records `data_snapshot_sha256`; replay refuses to run if `--data-dir` contains a *different* snapshot for the same `run_id`. `loop list --stale` flags old runs. |
| R8 | **Git commit drift** — replay runs against a commit that's been force-pushed away | Low | High | N6 captures `git rev-parse HEAD` *and* `git rev-parse --verify HEAD^{commit}`; replay refuses if current HEAD ≠ recorded commit. (Mirrors git's own "detached HEAD" warning.) |
| R9 | **multiprocessing + pytest interaction** — `Pool` inherits test fixtures, hangs the suite | Medium | Medium | All N3 tests use `multiprocessing.get_context("spawn")` explicitly; CI runs with `-p no:cacheprovider`; one smoke test runs the real Pool against 4 synthetic tasks. |
| R10 | **Parquet schema drift** — pyarrow version mismatch between run and replay | Low | Medium | Pin `pyarrow>=14,<16` in `pyproject.toml`; replay writes a `pyarrow_version.txt` to the run dir and refuses on major mismatch. |
| R11 | **Manifest YAML injection** — a malicious goal string injects YAML keys | Low | High | Use `yaml.safe_load` only; goal is stored as a string field, not parsed for nested keys. Goal string is length-capped at 4 KB. |
| R12 | **N5 report reveals trade ideas publicly** — committed report has `one_line_thesis` for top-5 | Low | Medium | Default `runs/` is local + gitignored by default. N6 commit message is "loop run <run_id>" not "alpha thesis". Documented in `loop --help`. v1.0 may add `--no-commit-thesis`. |
| R13 | **CPU-bound N3 dominates wall clock** — single fast machine gives N3 <1h; multi-day on Raspberry Pi | Low (single machine assumed) | Low | Documented minimum spec in README: 4 cores + 16 GB RAM. `loop --max-cores 2` lets slow hardware opt out of full parallel. |
| R14 | **Top-5 picks all fail Q7 (LLM judge SKIPs all)** → empty top5.json | Low | Medium | If `len(top5) < 5`, N5 still writes report.md noting "no Q7-passing strategies found"; user can re-run with `--judge-threshold 5` or `--no-judge`. |
| R15 | **Replay across Python versions** — replay written in 3.11, read in 3.13 | Low | Low | Parquet is the boundary format; dataclass schema is JSON in manifest; pyarrow handles cross-version. CI matrix runs Python 3.11 + 3.13 on the replay test. |

### 5.2 Cost & performance budget

| Component | Budget | Notes |
|-----------|--------|-------|
| N1 LLM | ≤ $0.01 | 1 planner call, ~500 tokens |
| N2 LLM | ≤ $0.02 | 1 planner call, ~1k tokens |
| N3 compute | 0 (CPU only) | dominated by wall clock, not cost |
| N4 LLM judge (Q7) | ≤ $4.50 | 500 tasks × ~$0.009/task on gpt-4o-mini |
| N4 diagnostics Q1–Q6 | 0 | deterministic |
| N5 LLM | ≤ $0.02 | 1 report call |
| N6 git | 0 | local commit only |
| **Total** | **≤ $5.00** | gate D hard cap |

If the user picks a premium model (Claude Sonnet 4, GPT-5.5), the
budget requires `--max-tasks 100` to stay under $5. Documented.

Wall-clock budget (8-core machine, ~30s/backtest):

| Stage | Budget |
|-------|--------|
| N1 | 60 s |
| N2 | 120 s |
| N3 | 4 h (500 × 30s / 8 cores ≈ 31 min; ×10 factor for slow CI) |
| N4 Q1–Q6 | 5 min |
| N4 Q7 | 45 min (500 × ~5s/sequential call) |
| N5 | 30 s |
| N6 | 30 s |
| **Total** | **≤ 5 h typical, 6 h cap** |

### 5.3 Known limitations (out of scope for v0.7)

- **No live trading integration.** N6 commits *reports*, not *trades*.
- **No multi-agent meta-eval.** That's v2.0.
- **No self-feedback.** One-shot loop; if N5 sees a failed plan, it
  does not re-invoke N2.
- **No distributed compute.** Single machine. Ray/Dask deferred.
- **No online learning.** Data is snapshot-loaded at N1.

### 5.4 Reversibility

v0.7 is **fully reversible**:

- All v0.5 + v0.6 files are unchanged.
- The new code lives entirely under `src/alphaloop/loop/` and
  `src/alphaloop/cli/loop.py`.
- Removing v0.7 is a 2-commit revert:
  `git revert` of the two v0.7 commits → the package is gone, the
  v0.6 `alphaloop report` still works.
- The 6 deterministic diagnostics + LLM judge are unchanged.
- All 206 v0.6 tests remain green.

This is intentional. If the loop MVP turns out to be unreliable or
harmful, we can rip it out without breaking the v1.0 acceptance
guarantee.

---

## 6. References

- `ROADMAP.md § v0.7` — original scope statement (this doc supersedes
  it for design detail).
- `docs/plans/v06-llm-judge.md` — pattern reference for: dataclass
  result schema (§ 3.1), FakeLLMClient pattern (§ 4.2), risk matrix
  layout (§ 5.1), reversibility section (§ 5.4), cost budget table
  (§ 5.2). The v0.7 design mirrors these patterns deliberately.
- `src/alphaloop/diagnostic/judge.py` — reused as N4 Q7.
- `src/alphaloop/strategies/factory.py` — N2 samples from this.
- `src/alphaloop/backtest/engine.py` — N3 worker wraps this.
- Jeff Dean, *Alpha Engineer* interview (2026-08-07), point #8
  ("AI builds AI") — the motivation for this feature.
- Lilian Weng, *Harness Engineering* (2026-07) — context for why the
  orchestrator is itself a first-class subsystem.
- Sakana AI "AI Scientist" (2024) — pattern reference for
  planner-in-fixed-skeleton hybrid.
- Karpathy, *LLM Wiki* — pattern reference for snapshotting every LLM
  call into `judge_calls/`.

---

## 7. Approval gate

Per the loop state file (`alphaloop-v07-hybrid-loop-design.md`):

> plan step 6: Coder state file update + report
> plan step 7: (after user OK) Commander dispatch development subagent

**This design doc must be reviewed and explicitly approved by the user
before any implementation work begins.** No code under
`src/alphaloop/loop/`, no `tests/test_loop.py`, no commits, no PRs —
only this document, awaiting OK.

Hard wall reminders (from state file):
1. Only write `docs/plans/v07-hybrid-loop.md` (this file).
2. Do not modify any existing alphaloop source or test.
3. Do not write `src/alphaloop/loop/*` yet.
4. Do not write `tests/test_loop.py` yet.
5. Do not commit anything.
6. Do not push to GitHub.
7. Do not connect to any broker or live account.