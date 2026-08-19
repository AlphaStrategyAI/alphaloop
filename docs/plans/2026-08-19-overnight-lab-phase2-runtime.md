# Overnight Lab Phase 2 — Durable Local Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local control plane so a user can `alphaloop start`, submit a frozen `ResearchSpec`, get a `run_id` immediately, and have the job keep running after the submitting CLI exits.

**Architecture:** New `src/alphaloop/runtime/` owns SQLite job state, atomic checkpoints, preflight, an in-process Job API, a loopback HTTP daemon, and a supervisor that spawns workers. Workers are a stopgap wrapper around `LoopRunner`; they must persist `JobStatus` separately from any termination letter and must not claim `FOUND`. Phase 3 replaces that wrapper. Do not build the morning Web UI, DSL, or `.asb` producer.

**Tech Stack:** Python 3.9+, pytest, PyYAML, stdlib `sqlite3` / `http.server` / `subprocess` / `threading` / `json`. No new third-party runtime dependency. Do not import FastAPI into `runtime/`.

## Global Constraints

- Local-first: default bind is `127.0.0.1`. Refuse non-loopback hosts.
- `JobStatus` and `ResearchOutcome` stay separate; never store a `LoopRunner` termination letter as a research outcome.
- A stopgap worker may reach `JobStatus.COMPLETED` but its research outcome is `INCONCLUSIVE` until Phase 3 supplies `GateEvidence` (`evidence_complete=False`).
- `FOUND` cannot be produced by the Web console, CLI, supervisor, or LoopRunner stopgap.
- Closing the browser or CLI must not stop a job; host sleep/power-off does. Preflight must disclose this using `HOST_CONSTRAINT` verbatim.
- A preflight error is not a research outcome: failed preflight must not insert a job row.
- `alphaloop.runtime` must not import `alphaloop.live`. Only `runtime/worker.py` may import `alphaloop.loop`.
- `alphaloop.loop` must not import `alphaloop.contracts.bundle` or `alphaloop.runtime`.
- Source of truth: `docs/requirements/product-positioning-requirements.md` and `docs/plans/overnight-research-lab-refactor.md`.

## File Structure

Design §2 listed `api.py`, `daemon.py`, `supervisor.py`, `checkpoint.py`. Split storage, preflight, worker, and HTTP client so each file has one responsibility:

- Create: `src/alphaloop/runtime/__init__.py`
- Create: `src/alphaloop/runtime/store.py` — SQLite `JobStore` / `JobRecord`
- Create: `src/alphaloop/runtime/checkpoint.py` — atomic checkpoint files
- Create: `src/alphaloop/runtime/preflight.py` — validation + host disclosure
- Create: `src/alphaloop/runtime/supervisor.py` — leases, heartbeat, restart, cancel
- Create: `src/alphaloop/runtime/api.py` — in-process Job API
- Create: `src/alphaloop/runtime/daemon.py` — HTTP server + process lifecycle
- Create: `src/alphaloop/runtime/worker.py` — LoopRunner stopgap process
- Create: `src/alphaloop/runtime/client.py` — loopback HTTP client for CLI
- Create: `src/alphaloop/cli/jobs.py` — `start` / `submit` / `status` / `cancel` / `resume`
- Modify: `src/alphaloop/cli/main.py` — register the new commands
- Test: `tests/runtime/`
- Modify: `docs/cli.md` — document the new commands (Task 7)

Default paths under `{data_dir}/.alphaloop/`:

- `state.db` — job index
- `daemon.pid` — daemon pid
- `daemon.json` — `{"host","port","pid"}`

Default listen: host `127.0.0.1`, port `8765`.

---

### Task 1: JobStore and JobRecord

**Files:**
- Create: `src/alphaloop/runtime/__init__.py`
- Create: `src/alphaloop/runtime/store.py`
- Test: `tests/runtime/test_store.py`

**Interfaces:**
- Consumes: `ResearchSpec`, `JobStatus`, `ResearchOutcome`, `RunLayout`, `derive_research_outcome`
- Produces:
  - `JobRecord` frozen dataclass with fields listed below
  - `JobStore(db_path: Path, data_dir: Path)`
  - `JobStore.create(spec: ResearchSpec, run_id: Optional[str] = None) -> JobRecord`
  - `JobStore.get(run_id: str) -> JobRecord` raises `KeyError`
  - `JobStore.list_jobs() -> tuple[JobRecord, ...]`
  - `JobStore.update_status(run_id: str, status: JobStatus, *, error: Optional[str] = None, worker_pid: Optional[int] = None) -> JobRecord`
  - `JobStore.set_heartbeat(run_id: str, *, pid: int, at: str) -> JobRecord`
  - `JobStore.increment_recovery(run_id: str) -> JobRecord`
  - `new_run_id() -> str` prefix `j_`

- [ ] **Step 1: Write the failing store tests**

Create `tests/runtime/test_store.py`:

```python
from __future__ import annotations

import dataclasses

import pytest
import yaml

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.research_spec import ResearchSpec, new_research_spec
from alphaloop.contracts.status import JobStatus, ResearchOutcome
from alphaloop.runtime.store import JobRecord, JobStore, new_run_id


def _spec() -> ResearchSpec:
    return new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="12-1 momentum",
        market_scope="US large-cap equities",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward", "vs_benchmark"),
        seed=7,
        time_budget_s=3600,
        cost_budget_usd=5.0,
    )


def test_create_returns_queued_none_immediately(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    assert job.status is JobStatus.QUEUED
    assert job.research_outcome is ResearchOutcome.NONE
    assert job.run_id.startswith("j_")
    assert job.recovery_attempts == 0
    loaded = store.get(job.run_id)
    assert loaded == job


def test_create_writes_research_spec_yaml(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    spec = _spec()
    job = store.create(spec)
    layout = RunLayout(tmp_path / job.run_id)
    payload = yaml.safe_load(layout.research_spec.read_text(encoding="utf-8"))
    assert ResearchSpec.from_dict(payload) == spec


def test_missing_job_raises_keyerror(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    with pytest.raises(KeyError):
        store.get("j_missing")


def test_update_status_persists_and_sets_inconclusive_on_failed(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    updated = store.update_status(job.run_id, JobStatus.FAILED, error="worker crashed")
    assert updated.status is JobStatus.FAILED
    assert updated.research_outcome is ResearchOutcome.INCONCLUSIVE
    assert updated.error == "worker crashed"
    assert store.get(job.run_id) == updated


def test_completed_without_evidence_is_inconclusive(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    updated = store.update_status(job.run_id, JobStatus.COMPLETED)
    assert updated.status is JobStatus.COMPLETED
    assert updated.research_outcome is ResearchOutcome.INCONCLUSIVE


def test_job_record_is_frozen():
    assert dataclasses.is_dataclass(JobRecord)
    assert JobRecord.__dataclass_params__.frozen is True


def test_new_run_id_is_unique():
    ids = {new_run_id() for _ in range(50)}
    assert len(ids) == 50
    assert all(item.startswith("j_") for item in ids)


def test_increment_recovery_and_heartbeat(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    beat = store.set_heartbeat(job.run_id, pid=4242, at="2026-08-19T00:00:00+00:00")
    assert beat.worker_pid == 4242
    assert beat.heartbeat_at == "2026-08-19T00:00:00+00:00"
    again = store.increment_recovery(job.run_id)
    assert again.recovery_attempts == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/runtime/test_store.py -v`

Expected: FAIL with `ModuleNotFoundError: alphaloop.runtime.store`

- [ ] **Step 3: Implement JobStore**

`src/alphaloop/runtime/__init__.py`:

```python
"""Durable local control plane (Phase 2)."""
```

`src/alphaloop/runtime/store.py` must:

- Use stdlib `sqlite3` with a `threading.Lock`.
- Create the table:

```sql
CREATE TABLE IF NOT EXISTS jobs (
  run_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  research_outcome TEXT NOT NULL,
  spec_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  worker_pid INTEGER,
  error TEXT,
  sealed_outcome TEXT,
  recovery_attempts INTEGER NOT NULL DEFAULT 0,
  heartbeat_at TEXT
)
```

- `JobRecord` fields: `run_id: str`, `status: JobStatus`, `research_outcome: ResearchOutcome`, `spec: ResearchSpec`, `created_at: str`, `updated_at: str`, `worker_pid: Optional[int]`, `heartbeat_at: Optional[str]`, `error: Optional[str]`, `sealed_outcome: Optional[ResearchOutcome]`, `recovery_attempts: int`
- `new_run_id()`: `"j_"` + UTC `YYYYMMDDTHHMMSSZ` + `"_"` + 8 hex chars from `secrets.token_hex(4)`
- timestamps: timezone-aware UTC ISO-8601
- `create`: insert `queued` / `NONE`, mkdir `data_dir/run_id`, write `research-spec.yaml` via `yaml.safe_dump(spec.to_dict(), sort_keys=True)`, mkdir `checkpoints/`
- `update_status`: recompute `research_outcome` with `derive_research_outcome(status, evidence_complete=False, all_gates_passed=False, sealed=sealed_outcome)`. Phase 2 never has gate evidence, so `COMPLETED`/`FAILED`/`CANCELLED` become `INCONCLUSIVE` unless `sealed_outcome is FOUND` (keep the sealed path in the call even though nothing seals FOUND yet)
- Do not import `alphaloop.loop` or `alphaloop.live`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/runtime/test_store.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/__init__.py src/alphaloop/runtime/store.py tests/runtime/test_store.py
git commit -m "feat(runtime): add SQLite job store and queued JobRecord"
```

---

### Task 2: Atomic checkpoints

**Files:**
- Create: `src/alphaloop/runtime/checkpoint.py`
- Test: `tests/runtime/test_checkpoint.py`

**Interfaces:**
- Consumes: `RunLayout`
- Produces:
  - `Checkpoint(seq: int, complete: bool, payload: dict)`
  - `write_checkpoint(layout: RunLayout, checkpoint: Checkpoint) -> Path`
  - `load_latest_complete(layout: RunLayout) -> Optional[Checkpoint]`
  - `HEARTBEAT_NAME = "heartbeat.json"`
  - `write_heartbeat(layout: RunLayout, pid: int, at: str) -> Path`
  - `read_heartbeat(layout: RunLayout) -> Optional[dict]`

- [ ] **Step 1: Write the failing checkpoint tests**

Create `tests/runtime/test_checkpoint.py`:

```python
from __future__ import annotations

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.runtime.checkpoint import (
    Checkpoint,
    load_latest_complete,
    read_heartbeat,
    write_checkpoint,
    write_heartbeat,
)


def test_write_and_load_latest_complete(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.checkpoints.mkdir(parents=True)
    write_checkpoint(layout, Checkpoint(seq=1, complete=True, payload={"step": "n1"}))
    write_checkpoint(layout, Checkpoint(seq=2, complete=False, payload={"step": "n2"}))
    write_checkpoint(layout, Checkpoint(seq=3, complete=True, payload={"step": "n3"}))
    latest = load_latest_complete(layout)
    assert latest is not None
    assert latest.seq == 3
    assert latest.payload == {"step": "n3"}


def test_incomplete_only_yields_none(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.checkpoints.mkdir(parents=True)
    write_checkpoint(layout, Checkpoint(seq=1, complete=False, payload={}))
    assert load_latest_complete(layout) is None


def test_partial_tmp_file_is_ignored(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.checkpoints.mkdir(parents=True)
    write_checkpoint(layout, Checkpoint(seq=1, complete=True, payload={"ok": True}))
    (layout.checkpoints / "ckpt-2.json.tmp").write_text("{not-json", encoding="utf-8")
    latest = load_latest_complete(layout)
    assert latest is not None
    assert latest.seq == 1


def test_heartbeat_round_trip(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir(parents=True)
    write_heartbeat(layout, pid=99, at="2026-08-19T00:00:00+00:00")
    assert read_heartbeat(layout) == {"pid": 99, "at": "2026-08-19T00:00:00+00:00"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/runtime/test_checkpoint.py -v`

Expected: FAIL with `ModuleNotFoundError: alphaloop.runtime.checkpoint`

- [ ] **Step 3: Implement checkpoints**

`write_checkpoint` must write `checkpoints/ckpt-{seq:06d}.json` using a sibling `.tmp` file then `Path.replace`. JSON keys: `seq`, `complete`, `payload`. `load_latest_complete` scans `ckpt-*.json` (not `.tmp`), skips `complete=false` and unreadable JSON, returns highest `seq`. Heartbeat writes `run_dir/heartbeat.json` the same tmp+replace way.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/runtime/test_checkpoint.py tests/runtime/test_store.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/checkpoint.py tests/runtime/test_checkpoint.py
git commit -m "feat(runtime): add atomic checkpoint and heartbeat files"
```

---

### Task 3: Preflight and host-constraint disclosure

**Files:**
- Create: `src/alphaloop/runtime/preflight.py`
- Test: `tests/runtime/test_preflight.py`

**Interfaces:**
- Consumes: `ResearchSpec`, `ALLOWED_PROFILES`
- Produces:
  - `HOST_CONSTRAINT` exactly:

```text
The host must remain awake while a local worker is running. Closing the browser or terminal does not stop a job, but suspending or powering off the host stops computation.
```

  - `PreflightResult(ok: bool, errors: tuple[str, ...], warnings: tuple[str, ...], host_constraint: str)`
  - `preflight(spec: ResearchSpec, data_dir: Path, *, min_free_bytes: int = 67108864) -> PreflightResult`

- [ ] **Step 1: Write the failing preflight tests**

Create `tests/runtime/test_preflight.py`:

```python
from __future__ import annotations

from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.runtime.preflight import HOST_CONSTRAINT, preflight


def _spec(**overrides):
    payload = dict(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="12-1 momentum",
        market_scope="US large-cap equities",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward", "vs_benchmark"),
        seed=7,
        time_budget_s=3600,
        cost_budget_usd=5.0,
    )
    payload.update(overrides)
    return new_research_spec(**payload)


def test_host_constraint_text_is_locked():
    assert HOST_CONSTRAINT == (
        "The host must remain awake while a local worker is running. "
        "Closing the browser or terminal does not stop a job, but "
        "suspending or powering off the host stops computation."
    )


def test_ok_spec_includes_host_constraint(tmp_path):
    result = preflight(_spec(), tmp_path)
    assert result.ok is True
    assert result.errors == ()
    assert result.host_constraint == HOST_CONSTRAINT


def test_empty_hard_gates_rejected(tmp_path):
    result = preflight(_spec(hard_gates=()), tmp_path)
    assert result.ok is False
    assert any("hard gate" in err.lower() for err in result.errors)
    assert result.host_constraint == HOST_CONSTRAINT


def test_zero_time_budget_rejected(tmp_path):
    result = preflight(_spec(time_budget_s=0), tmp_path)
    assert result.ok is False
    assert any("time" in err.lower() for err in result.errors)


def test_data_dir_that_is_a_file_rejected(tmp_path):
    target = tmp_path / "blocked"
    target.write_text("not-a-directory", encoding="utf-8")
    result = preflight(_spec(), target)
    assert result.ok is False
    assert any("writ" in err.lower() or "data" in err.lower() for err in result.errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/runtime/test_preflight.py -v`

Expected: FAIL with `ModuleNotFoundError: alphaloop.runtime.preflight`

- [ ] **Step 3: Implement preflight**

Reject when: `hard_gates` empty; `time_budget_s <= 0`; `cost_budget_usd < 0`; `data_dir` cannot be created or is not writable; `shutil.disk_usage(data_dir).free < min_free_bytes` (error mentions disk). Always set `host_constraint=HOST_CONSTRAINT`, including failures. Do not insert jobs. Do not import `loop` or `live`. Unsupported `market_profile` is already rejected by `Hypothesis`; do not catch that here — callers construct a valid spec first.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/runtime/test_preflight.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/preflight.py tests/runtime/test_preflight.py
git commit -m "feat(runtime): add preflight and locked host-constraint disclosure"
```

---

### Task 4: Supervisor heartbeat, restart, and cancel

**Files:**
- Create: `src/alphaloop/runtime/supervisor.py`
- Test: `tests/runtime/test_supervisor.py`

**Interfaces:**
- Consumes: `JobStore`, `RunLayout`, checkpoint/heartbeat helpers
- Produces:
  - `WorkerHandle` protocol: `spawn(run_id: str, data_dir: Path) -> int`, `poll(pid: int) -> Optional[int]`, `terminate(pid: int) -> None`
  - `Supervisor(store: JobStore, data_dir: Path, worker: WorkerHandle, *, heartbeat_timeout_s: float = 15.0, max_recovery: int = 3)`
  - `Supervisor.tick() -> None`
  - `Supervisor.request_cancel(run_id: str) -> JobRecord`
  - `MAX_RECOVERY_ATTEMPTS = 3`

`poll` returns `None` if the worker is still running, else the integer exit code.

- [ ] **Step 1: Write the failing supervisor tests**

Create `tests/runtime/test_supervisor.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.contracts.status import JobStatus, ResearchOutcome
from alphaloop.runtime.checkpoint import write_heartbeat
from alphaloop.runtime.store import JobStore
from alphaloop.runtime.supervisor import Supervisor
from alphaloop.contracts.artifacts import RunLayout


def _spec():
    return new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="12-1 momentum",
        market_scope="US large-cap equities",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward", "vs_benchmark"),
        seed=7,
        time_budget_s=3600,
        cost_budget_usd=5.0,
    )


class FakeWorker:
    def __init__(self) -> None:
        self.running: Dict[int, str] = {}
        self.exit_codes: Dict[int, int] = {}
        self.spawned: list[str] = []
        self.terminated: list[int] = []
        self._next_pid = 1000

    def spawn(self, run_id: str, data_dir: Path) -> int:
        pid = self._next_pid
        self._next_pid += 1
        self.running[pid] = run_id
        self.spawned.append(run_id)
        layout = RunLayout(Path(data_dir) / run_id)
        layout.run_dir.mkdir(parents=True, exist_ok=True)
        write_heartbeat(layout, pid=pid, at="2026-08-19T00:00:00+00:00")
        return pid

    def poll(self, pid: int) -> Optional[int]:
        if pid in self.exit_codes:
            return self.exit_codes[pid]
        if pid in self.running:
            return None
        return 1

    def terminate(self, pid: int) -> None:
        self.terminated.append(pid)
        self.running.pop(pid, None)
        self.exit_codes[pid] = -15

    def crash(self, pid: int) -> None:
        self.running.pop(pid, None)
        self.exit_codes[pid] = 1

    def succeed(self, pid: int) -> None:
        self.running.pop(pid, None)
        self.exit_codes[pid] = 0


def test_tick_starts_queued_job(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, heartbeat_timeout_s=60.0)
    job = store.create(_spec())
    sup.tick()
    running = store.get(job.run_id)
    assert running.status is JobStatus.RUNNING
    assert running.research_outcome is ResearchOutcome.NONE
    assert worker.spawned == [job.run_id]


def test_successful_exit_is_completed_inconclusive(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker)
    job = store.create(_spec())
    sup.tick()
    pid = store.get(job.run_id).worker_pid
    assert pid is not None
    worker.succeed(pid)
    sup.tick()
    done = store.get(job.run_id)
    assert done.status is JobStatus.COMPLETED
    assert done.research_outcome is ResearchOutcome.INCONCLUSIVE


def test_crash_restarts_until_max_then_fails(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, max_recovery=2, heartbeat_timeout_s=60.0)
    job = store.create(_spec())
    sup.tick()
    pid1 = store.get(job.run_id).worker_pid
    worker.crash(pid1)
    sup.tick()
    assert store.get(job.run_id).status is JobStatus.RUNNING
    assert store.get(job.run_id).recovery_attempts == 1
    pid2 = store.get(job.run_id).worker_pid
    worker.crash(pid2)
    sup.tick()
    failed = store.get(job.run_id)
    assert failed.status is JobStatus.FAILED
    assert failed.research_outcome is ResearchOutcome.INCONCLUSIVE
    assert failed.recovery_attempts == 2


def test_cancel_kills_worker(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker)
    job = store.create(_spec())
    sup.tick()
    cancelled = sup.request_cancel(job.run_id)
    assert cancelled.status is JobStatus.CANCELLED
    assert cancelled.research_outcome is ResearchOutcome.INCONCLUSIVE
    assert worker.terminated != []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/runtime/test_supervisor.py -v`

Expected: FAIL with `ModuleNotFoundError: alphaloop.runtime.supervisor`

- [ ] **Step 3: Implement Supervisor**

`tick()`:

1. For each `queued` job: `spawn`, `update_status(..., RUNNING, worker_pid=pid)`, `set_heartbeat`.
2. For each `running` job: `code = worker.poll(pid)`.
   - `code == 0` → `update_status(..., COMPLETED)`
   - `code not in (None, 0)` or missing heartbeat older than `heartbeat_timeout_s`: if `recovery_attempts < max_recovery`, `increment_recovery` and spawn again; else `update_status(..., FAILED, error="worker recovery exhausted")`
3. Stale heartbeat: compare `heartbeat.json` `at` (or store `heartbeat_at`) to now. Tests that write a fresh heartbeat and `heartbeat_timeout_s=60` must not look stale. Crash-via-`poll` exit 1 is enough for the recovery test; do not also require a stale heartbeat for that test.

`request_cancel`: if already terminal (`completed`/`failed`/`cancelled`), return current record without respawning. Else `terminate` pid if any, then `update_status(..., CANCELLED)`.

`Supervisor.__init__` must store the handle as `self.worker` (Task 5 tests read `api.supervisor.worker`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/runtime/test_supervisor.py tests/runtime/test_store.py tests/runtime/test_checkpoint.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/supervisor.py tests/runtime/test_supervisor.py
git commit -m "feat(runtime): add worker supervisor with restart and cancel"
```

---

### Task 5: In-process Job API and loopback HTTP

**Files:**
- Create: `src/alphaloop/runtime/api.py`
- Create: `src/alphaloop/runtime/daemon.py`
- Create: `src/alphaloop/runtime/client.py`
- Test: `tests/runtime/test_api.py`
- Test: `tests/runtime/test_http.py`

**Interfaces:**
- Consumes: `JobStore`, `Supervisor`, `preflight`, `HOST_CONSTRAINT`, `ResearchSpec`
- Produces:
  - `JobAPI(store: JobStore, supervisor: Supervisor, data_dir: Path)`
  - `JobAPI.create_run(spec: ResearchSpec) -> dict` returns immediately
  - `JobAPI.get_run(run_id: str) -> dict` raises `KeyError`
  - `JobAPI.cancel_run(run_id: str) -> dict`
  - `JobAPI.resume_run(run_id: str) -> dict`
  - `PreflightRejected(ValueError)`
  - `DaemonAlreadyRunning(RuntimeError)`
  - `UnsupportedBindHost(ValueError)`
  - `DEFAULT_HOST = "127.0.0.1"`
  - `DEFAULT_PORT = 8765`
  - `start_http_server(api: JobAPI, host: str, port: int) -> socketserver.ThreadingTCPServer` serving in a daemon thread
  - `JobClient(base_url: str)` with `create_run` / `get_run` / `cancel_run` / `resume_run` / `healthz`
  - HTTP:
    - `GET /healthz` → `{"status":"ok"}`
    - `POST /v1/jobs` JSON body = `spec.to_dict()`
    - `GET /v1/jobs/{run_id}`
    - `POST /v1/jobs/{run_id}/cancel`
    - `POST /v1/jobs/{run_id}/resume`
  - Public job dict keys: `run_id`, `status`, `research_outcome`, `spec_id`, `error`, `recovery_attempts`, `host_constraint` (create only)

`create_run` must call `preflight` first. On failure raise `PreflightRejected` with `result.errors`; HTTP status 400. On success `store.create` then return without waiting for `tick`.

`resume_run`: if `cancelled` or `completed`, raise `ValueError`. If `failed` or `running`/`queued`, set status to `queued` (clear error) so the next `tick` spawns; HTTP 409 for illegal resume.

Refuse `host` other than `127.0.0.1` or `localhost` by raising `UnsupportedBindHost`.

- [ ] **Step 1: Write the failing API and HTTP tests**

`tests/runtime/test_api.py`:

```python
from __future__ import annotations

import pytest

from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.contracts.status import JobStatus, ResearchOutcome
from alphaloop.runtime.api import JobAPI, PreflightRejected
from alphaloop.runtime.preflight import HOST_CONSTRAINT
from alphaloop.runtime.store import JobStore
from alphaloop.runtime.supervisor import Supervisor
from tests.runtime.test_supervisor import FakeWorker, _spec


def _api(tmp_path) -> JobAPI:
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, heartbeat_timeout_s=60.0)
    return JobAPI(store, sup, tmp_path)


def test_create_run_returns_immediately_without_starting_worker(tmp_path):
    api = _api(tmp_path)
    payload = api.create_run(_spec())
    assert payload["status"] == JobStatus.QUEUED.value
    assert payload["research_outcome"] == ResearchOutcome.NONE.value
    assert payload["host_constraint"] == HOST_CONSTRAINT
    assert payload["run_id"].startswith("j_")
    assert api.supervisor.worker.spawned == []


def test_create_run_rejects_empty_gates_without_inserting_job(tmp_path):
    api = _api(tmp_path)
    spec = new_research_spec(
        statement="x",
        economic_logic="x",
        signal_mechanism="x",
        market_scope="x",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=(),
        seed=1,
        time_budget_s=10,
        cost_budget_usd=1.0,
    )
    with pytest.raises(PreflightRejected):
        api.create_run(spec)
    assert api.store.list_jobs() == ()


def test_get_cancel_resume(tmp_path):
    api = _api(tmp_path)
    created = api.create_run(_spec())
    run_id = created["run_id"]
    api.supervisor.tick()
    assert api.get_run(run_id)["status"] == JobStatus.RUNNING.value
    cancelled = api.cancel_run(run_id)
    assert cancelled["status"] == JobStatus.CANCELLED.value
    assert cancelled["research_outcome"] == ResearchOutcome.INCONCLUSIVE.value
    with pytest.raises(ValueError):
        api.resume_run(run_id)
```

`tests/runtime/test_http.py`:

```python
from __future__ import annotations

import pytest

from alphaloop.runtime.client import JobClient
from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, UnsupportedBindHost
from alphaloop.runtime.store import JobStore
from alphaloop.runtime.supervisor import Supervisor
from alphaloop.runtime.api import JobAPI
from tests.runtime.test_supervisor import FakeWorker, _spec


def test_http_create_get_cancel(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, heartbeat_timeout_s=60.0)
    api = JobAPI(store, sup, tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    client = JobClient(f"http://{host}:{port}")
    try:
        assert client.healthz()["status"] == "ok"
        created = client.create_run(_spec())
        fetched = client.get_run(created["run_id"])
        assert fetched["run_id"] == created["run_id"]
        cancelled = client.cancel_run(created["run_id"])
        assert cancelled["status"] == "cancelled"
    finally:
        server.shutdown()


def test_non_loopback_bind_rejected(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    with pytest.raises(UnsupportedBindHost):
        start_http_server(api, "0.0.0.0", 8765)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/runtime/test_api.py tests/runtime/test_http.py -v`

Expected: FAIL with missing `alphaloop.runtime.api` / `daemon` / `client`

- [ ] **Step 3: Implement JobAPI, stdlib HTTP, and client**

Use `http.server.BaseHTTPRequestHandler` + `socketserver.ThreadingTCPServer`. `start_http_server(..., port=0)` must bind an ephemeral port. JSON request bodies; UTF-8. Unknown paths 404. `JobClient` uses `urllib.request`. Do not import FastAPI. Do not import `loop` or `live`.

`JobAPI` must keep `.store` and `.supervisor` attributes (tests access them).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/runtime/ -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/api.py src/alphaloop/runtime/daemon.py src/alphaloop/runtime/client.py tests/runtime/test_api.py tests/runtime/test_http.py
git commit -m "feat(runtime): add Job API and loopback HTTP daemon"
```

---

### Task 6: CLI, detached daemon, and LoopRunner stopgap worker

**Files:**
- Create: `src/alphaloop/runtime/worker.py`
- Create: `src/alphaloop/cli/jobs.py`
- Modify: `src/alphaloop/cli/main.py`
- Modify: `src/alphaloop/runtime/daemon.py` (pidfile, detach, serve loop)
- Test: `tests/runtime/test_worker.py`
- Test: `tests/runtime/test_cli_jobs.py`
- Test: `tests/runtime/test_daemon_detach.py`

**Interfaces:**
- Consumes: Job API / client / store / supervisor / `LoopRunner`
- Produces:
  - `stopgap_terminal_outcome() -> ResearchOutcome` always `INCONCLUSIVE` via `derive_research_outcome(JobStatus.COMPLETED, False, False)`
  - `run_worker(run_id: str, data_dir: Path) -> int` used as `python -m alphaloop.runtime.worker --run-id ID --data-dir DIR`
  - `ProcessWorker` implementing `WorkerHandle` via `subprocess.Popen([sys.executable, "-m", "alphaloop.runtime.worker", ...])`
  - `serve_forever(data_dir: Path, host: str, port: int) -> None` writes pidfile + `daemon.json`, runs supervisor on a background thread (`tick` every 0.5s), serves HTTP
  - `spawn_detached_daemon(data_dir: Path, host: str, port: int) -> dict` starts a child with `start_new_session=True` that calls `serve_forever`
  - CLI:
    - `alphaloop start [--data-dir DIR] [--host 127.0.0.1] [--port 8765] [--detach]`
    - `alphaloop submit --spec PATH [--data-dir DIR]`
    - `alphaloop status RUN_ID [--data-dir DIR]`
    - `alphaloop cancel RUN_ID [--data-dir DIR]`
    - `alphaloop resume RUN_ID [--data-dir DIR]`
  - CLI `submit` prints `run_id` and `HOST_CONSTRAINT` and returns 0 without waiting for completion
  - If daemon is down, submit/status/cancel/resume exit 2 and tell the user to run `alphaloop start`

`run_worker` may call `LoopRunner`. It must write checkpoint `seq=1 complete=True` before invoking the runner, heartbeat at start, and ignore `summary.termination_reason` when finishing (the supervisor marks COMPLETED; worker exit 0 is enough). To keep unit tests fast, `run_worker` should accept an optional `runner_factory` used only in tests; the module default may construct `LoopRunner(goal=spec.hypothesis.statement, run_id=run_id, seed=spec.seed, budget_usd=spec.cost_budget_usd, timeout_s=spec.time_budget_s, data_dir=str(data_dir), dry_run=True)` so a real subprocess cannot run a 6-hour DAG. Document `dry_run=True` as Phase-2 stopgap.

Do not change `alphaloop loop` behavior in this task.

- [ ] **Step 1: Write the failing worker and CLI tests**

`tests/runtime/test_worker.py`:

```python
from __future__ import annotations

from alphaloop.contracts.status import JobStatus, ResearchOutcome, derive_research_outcome
from alphaloop.runtime.worker import stopgap_terminal_outcome


def test_stopgap_never_claims_found():
    outcome = stopgap_terminal_outcome()
    assert outcome is ResearchOutcome.INCONCLUSIVE
    assert outcome is derive_research_outcome(JobStatus.COMPLETED, False, False)
    assert outcome is not ResearchOutcome.FOUND


def test_stopgap_does_not_use_termination_letter():
    assert stopgap_terminal_outcome() != "A"
    assert getattr(stopgap_terminal_outcome(), "value", None) != "target found"
```

`tests/runtime/test_cli_jobs.py`:

```python
from __future__ import annotations

import yaml

from alphaloop.cli.main import create_parser, main
from alphaloop.runtime.preflight import HOST_CONSTRAINT
from tests.runtime.test_supervisor import _spec


def test_parser_has_runtime_commands():
    parser = create_parser()
    assert "start" in parser.format_help()
    assert "submit" in parser.format_help()


def test_submit_without_daemon_fails(tmp_path, capsys):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    rc = main(["submit", "--spec", str(spec_path), "--data-dir", str(tmp_path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "alphaloop start" in err


def test_submit_returns_run_id_and_host_constraint(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    try:
        rc = main(["submit", "--spec", str(spec_path), "--data-dir", str(tmp_path)])
        captured = capsys.readouterr()
        assert rc == 0
        assert HOST_CONSTRAINT in captured.out
        assert "j_" in captured.out
    finally:
        server.shutdown()
```

`tests/runtime/test_daemon_detach.py`:

```python
from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path

import yaml

from alphaloop.runtime.client import JobClient
from alphaloop.runtime.daemon import spawn_detached_daemon
from tests.runtime.test_supervisor import _spec


def test_submit_survives_parent_exit(tmp_path):
    meta = spawn_detached_daemon(tmp_path, "127.0.0.1", 0)
    client = JobClient(f"http://{meta['host']}:{meta['port']}")
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            client.healthz()
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise AssertionError("daemon did not start")
    created = client.create_run(_spec())
    os.kill(os.getpid(), 0)  # parent still here; job must already be persisted
    fetched = client.get_run(created["run_id"])
    assert fetched["run_id"] == created["run_id"]
    os.kill(meta["pid"], signal.SIGTERM)
```

Also add `write_daemon_meta(data_dir, host, port, pid)` used by CLI to discover the daemon. `spawn_detached_daemon` with `port=0` must pick a free port, put it in `daemon.json`, and start a child that actually listens there.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/runtime/test_worker.py tests/runtime/test_cli_jobs.py tests/runtime/test_daemon_detach.py -v`

Expected: FAIL on missing worker/CLI/daemon helpers

- [ ] **Step 3: Implement worker, daemon lifecycle, and CLI**

`read_daemon_meta(data_dir)` reads `{data_dir}/.alphaloop/daemon.json`. CLI job commands use that to build `JobClient`. `start --detach` calls `spawn_detached_daemon` and prints host/port/pid. `start` without `--detach` calls `serve_forever` (tests should not invoke the blocking path).

Register commands in `create_parser` and dispatch in `main` the same way `export` uses `parsed.func`.

Placeholder GET `/` may return `text/plain` `alphaloop control plane` — not a real Web UI.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/runtime/ tests/test_package_identity.py tests/test_cli.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/worker.py src/alphaloop/runtime/daemon.py src/alphaloop/cli/jobs.py src/alphaloop/cli/main.py tests/runtime/test_worker.py tests/runtime/test_cli_jobs.py tests/runtime/test_daemon_detach.py
git commit -m "feat(runtime): add alphaloop start/submit and stopgap worker"
```

---

### Task 7: Import-graph guards, docs, and regression sweep

**Files:**
- Test: `tests/runtime/test_import_graph.py`
- Modify: `tests/test_package_identity.py` (CLI help mentions `start`)
- Modify: `docs/cli.md`
- Modify: `docs/plans/overnight-research-lab-refactor.md` (point Phase 2 at this plan)
- Modify: `docs/requirements/product-positioning-requirements.md` §13 next-cycle sentence

**Interfaces:**
- Consumes: runtime package tree
- Produces: guards and docs only

- [ ] **Step 1: Write the failing import-graph and help tests**

`tests/runtime/test_import_graph.py`:

```python
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "src" / "alphaloop"


def _iter_py(package: str):
    folder = ROOT / package
    if not folder.exists():
        return
    for path in folder.rglob("*.py"):
        yield path, path.read_text(encoding="utf-8")


def test_runtime_does_not_import_live():
    for path, text in _iter_py("runtime"):
        assert "alphaloop.live" not in text, path
        assert "from ..live" not in text, path
        assert "from .live" not in text, path


def test_only_worker_may_import_loop():
    for path, text in _iter_py("runtime"):
        if path.name == "worker.py":
            continue
        assert "alphaloop.loop" not in text, path
        assert "from ..loop" not in text, path


def test_loop_does_not_import_runtime_or_bundle():
    for path, text in _iter_py("loop"):
        assert "alphaloop.runtime" not in text, path
        assert "alphaloop.contracts.bundle" not in text, path
```

In `tests/test_package_identity.py` add:

```python
def test_cli_help_lists_start(capsys):
    rc = main([])
    assert rc == 1
    out = capsys.readouterr().out
    assert "start" in out
    assert "submit" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/runtime/test_import_graph.py tests/test_package_identity.py::test_cli_help_lists_start -v`

Expected: FAIL on missing test / missing `start` in help until Task 6 landed; after Task 6, import-graph should already pass if worker isolation was followed. If Task 6 leaked `loop` imports, this task fails and must be fixed here.

- [ ] **Step 3: Add docs pointers and any missing guards**

Update `docs/cli.md` global usage to include `{start, submit, status, cancel, resume, ...}` and add short sections for those commands. Point design §5 Phase 2 at this plan file. Change requirements §13 last paragraph from "begin with item 1" to "item 1 is implemented; item 2 is this runtime plan".

- [ ] **Step 4: Run the non-integration sweep**

Run: `python3 -m pytest tests/ -m "not integration" -q`

Expected: all previously passing tests still pass, plus the new runtime tests.

- [ ] **Step 5: Commit**

```bash
git add tests/runtime/test_import_graph.py tests/test_package_identity.py docs/cli.md docs/plans/overnight-research-lab-refactor.md docs/requirements/product-positioning-requirements.md
git commit -m "test(runtime): lock import graph and document start/submit CLI"
```

---

## Self-review

1. **Spec coverage:** Job API create/get/cancel/resume, daemon, supervisor, checkpoints, recovery, host disclosure, loopback bind, immediate `run_id`, CLI not holding the job, LoopRunner stopgap without `FOUND`, no `live` import.
2. **Out of scope (no task):** DSL, epistemic stop, market-profile engines, morning Web, `.asb` producer, Agent Skill, MCP, FastAPI, changing `alphaloop loop`.
3. **Types:** `JobRecord`, `Checkpoint`, `PreflightResult`, `JobAPI`, `JobClient`, `WorkerHandle`, `HOST_CONSTRAINT`, `DEFAULT_HOST`, `DEFAULT_PORT` are consistent across tasks.
