# Morning console real-daemon Web E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unit tests talk only to a real overnight-lab daemon; e2e tests drive the packaged morning page in Chromium against that same daemon, covering submit, outcomes, cancel/resume/replay/export, and no gate override.

**Architecture:** `spawn_detached_daemon` starts JobAPI + Supervisor + `ProcessWorker` on loopback. Playwright loads `/`. CLI uses `read_daemon_meta(data_dir)`. Isolated `tmp_path` per test.

**Tech Stack:** pytest, playwright (optional extra `e2e`), existing `alphaloop` daemon/CLI.

## Global Constraints

- Unit tests: real daemon only; no `FakeWorker`; no browser required.
- E2E tests: real packaged Web page **and** real daemon; no `FakeWorker`.
- Do not invent `FOUND`. Do not synthesize RNG prices.
- `HOST_CONSTRAINT` text is locked.
- Frozen FastAPI/Vite SPA and `alphaloop.live` are out of scope.
- Existing `FakeWorker` supervisor isolation tests stay.
- Default CI unit job must exclude `e2e`.

---

### Task 1: Tooling, markers, shared fixtures

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/conftest.py`
- Modify: `.github/workflows/pytest.yml`
- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/conftest.py`
- Modify: `mkdocs.yml` (nav entry for the design doc)
- Modify: `docs/plans/2026-08-19-overnight-lab-remaining-work.md` (pointer only if a verification row exists)

**Interfaces:**
- Consumes: `spawn_detached_daemon(data_dir, "127.0.0.1", 0)`
- Produces: fixture `real_daemon(tmp_path) -> dict` with keys `data_dir`, `host`, `port`, `pid`, `base_url`

- [ ] **Step 1: Add extra and markers**

In `pyproject.toml` `[project.optional-dependencies]` add:

```toml
e2e = ["playwright>=1.40"]
```

In `tests/conftest.py` `pytest_configure` add:

```python
config.addinivalue_line(
    "markers",
    "e2e: real packaged Web page plus real daemon (Playwright)",
)
```

- [ ] **Step 2: Shared daemon fixture**

`tests/e2e/conftest.py` (also importable from unit tests via a small helper in `tests/runtime/real_daemon.py` if needed):

```python
import os
import signal
import time

import pytest

from alphaloop.runtime.daemon import spawn_detached_daemon


@pytest.fixture
def real_daemon(tmp_path):
    meta = spawn_detached_daemon(tmp_path, "127.0.0.1", 0)
    meta = dict(meta)
    meta["data_dir"] = tmp_path
    meta["base_url"] = f"http://{meta['host']}:{meta['port']}"
    try:
        yield meta
    finally:
        os.kill(meta["pid"], signal.SIGTERM)
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                os.kill(meta["pid"], 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
```

- [ ] **Step 3: CI unit job excludes e2e; add e2e job**

Unit step becomes:

```
python -m pytest -m "not integration and not llm and not e2e" --ignore=tests/integration
```

New job `e2e` installs `.[dev,e2e]`, `python -m playwright install --with-deps chromium`, then `python -m pytest -m e2e`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml tests/conftest.py tests/e2e/conftest.py .github/workflows/pytest.yml mkdocs.yml
git commit -m "test: add real-daemon fixtures and e2e marker"
```

---

### Task 2: Unit tests against the real daemon

**Files:**
- Create: `tests/runtime/test_real_daemon_http.py`

**Interfaces:**
- Consumes: `real_daemon` fixture (move helper to `tests/runtime/real_daemon.py` so both packages can import it)
- Produces: U1–U5 passing without Playwright

- [ ] **Step 1: Write failing tests U1–U5** using `urllib` YAML POST to `real_daemon["base_url"]`.
- [ ] **Step 2: Run them; they should fail only if daemon wiring is wrong (likely pass on current code).**
- [ ] **Step 3: Commit**

```bash
git add tests/runtime/real_daemon.py tests/runtime/test_real_daemon_http.py
git commit -m "test(runtime): real daemon HTTP submit and preflight"
```

---

### Task 3: Playwright e2e matrix E1–E12

**Files:**
- Create: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: `real_daemon`, fixture parquet + `DatasetRef`, `alphaloop.cli.jobs` via `python -m alphaloop.cli.main`
- Produces: marked `e2e` tests covering E1–E12

- [ ] **Step 1: Write tests that launch Chromium, `page.goto(base_url + "/")`, fill `#spec-yaml`, click `#submit-job`.**
- [ ] **Step 2: CLI subprocess uses `--data-dir` pointing at the same tmp path.**
- [ ] **Step 3: Wait for terminal job with timeout 60s; accept any of the three outcome tokens.**
- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_morning_console.py
git commit -m "test(e2e): morning console against real daemon"
```

---

### Task 4: Docs pointer

**Files:**
- Modify: `docs/plans/2026-08-19-overnight-lab-phase11-verification.md` (one sentence pointing at this e2e plan)
- Modify: `mkdocs.yml`

- [ ] **Step 1: Add nav + pointer. `mkdocs build --strict`.**
- [ ] **Step 2: Commit**
