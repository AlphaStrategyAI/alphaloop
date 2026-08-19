# Overnight Lab Phase 4 — Morning Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve a packaged morning Web console from `alphaloop start` so a user can identify the conclusion, primary evidence, and stop reason in five minutes — without Node on PATH and without any way to override hard gates.

**Architecture:** The Phase 2 loopback daemon serves static HTML/CSS/JS shipped inside `alphaloop.webui.static`. The page is a read-only client of the Job API. A small `runtime/morning.py` assembler reads sealed artifacts (`evidence/gates.json`, `trial-ledger.jsonl`, `recommendations.json`) into a morning payload. The existing Vite TopFive SPA remains for `alphaloop loop` compatibility and is not the overnight-lab home page.

**Tech Stack:** Python 3.9+, stdlib `http.server` / `importlib.resources`, vanilla HTML/CSS/JS (no Node, no Vite build at runtime), pytest, Phase 1–3 contracts/runtime/protocol.

## Global Constraints

- Home page leads with `FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE` (or `NONE` while running). Copy must use those exact tokens.
- Web console does not execute research and cannot override evidence gates. No PATCH/PUT/POST that mutates `GateEvidence` or `success_criteria.hard_gates`.
- End users do not install Node. Assets are packaged with the Python package.
- Bind remains loopback (`127.0.0.1`) by default. Do not expose research data off-box.
- Do not import `alphaloop.live`. Do not import FastAPI `alphaloop.webui.api` from `runtime/`.
- `alphaloop.protocol` must not import `webui` or `runtime`.
- JobStatus and ResearchOutcome stay separate. UI must not display LoopRunner letters A/B/C/D as outcomes.
- `FOUND` is display-only of sealed evidence; the UI cannot mint it.
- Tests use the Job API / HTTP daemon; no network; no browser driver required.
- Source of truth: `docs/requirements/product-positioning-requirements.md` §4.3 / §5.2 and `docs/design/overnight-research-lab-refactor.md`.

## File Structure

- Create: `src/alphaloop/runtime/morning.py` — assemble morning payload from job + artifacts
- Create: `src/alphaloop/webui/static/__init__.py`
- Create: `src/alphaloop/webui/static/index.html`
- Create: `src/alphaloop/webui/static/app.js`
- Create: `src/alphaloop/webui/static/styles.css`
- Modify: `src/alphaloop/runtime/api.py` — `list_jobs`, richer `get_run`
- Modify: `src/alphaloop/runtime/daemon.py` — static files, `GET /v1/jobs`, HTML `/`
- Modify: `src/alphaloop/runtime/client.py` — `list_jobs`
- Test: `tests/runtime/test_morning.py`
- Test: `tests/runtime/test_static_console.py`
- Modify: `tests/runtime/test_api.py`, `tests/runtime/test_http.py`
- Modify: docs pointers in design §5 Phase 4 and requirements §13

---

### Task 1: Morning payload assembler

**Files:**
- Create: `src/alphaloop/runtime/morning.py`
- Test: `tests/runtime/test_morning.py`

**Interfaces:**
- `STOP_REASON_ALL_GATES_PASSED = "all_gates_passed"`
- `STOP_REASON_HARD_GATE_FAILED = "hard_gate_failed"`
- `STOP_REASON_INCOMPLETE_EVIDENCE = "incomplete_evidence"`
- `morning_view(job: JobRecord, data_dir: Path) -> dict`
- Always includes: `run_id`, `status`, `research_outcome`, `spec_id`, `error`, `recovery_attempts`, `hypothesis` (dict from spec), `evidence` (dict or `None`), `funnel` (`{"dominant_failures": [gate name, ...]}`), `revisions` (list of trial-ledger objects), `queued_hypotheses` (list), `stop_reason` (`str | None`)
- `research_outcome` is `job.research_outcome.value` — never a LoopRunner letter
- Missing/corrupt `gates.json` → `evidence is None`, do not invent `FOUND`
- `stop_reason`: `NONE` → `None`; `FOUND` → `all_gates_passed`; `NO_EVIDENCE` → `hard_gate_failed`; `INCONCLUSIVE` → `incomplete_evidence`
- `funnel.dominant_failures` is the names of required gates whose `passed` is False; empty if no evidence
- `queued_hypotheses` from `recommendations.json` key `queued_hypotheses`, else `[]`

- [ ] **Step 1: Write failing tests** covering FOUND with passing gates.json, INCONCLUSIVE with missing gates, NO_EVIDENCE with one failed gate, corrupt gates.json does not claim FOUND, revisions from trial-ledger, queued list from recommendations.

- [ ] **Step 2: Run tests, expect FAIL** (`ModuleNotFoundError: alphaloop.runtime.morning`)

- [ ] **Step 3: Implement morning.py**

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit** `feat(runtime): assemble morning review payload from sealed artifacts`

---

### Task 2: Job API list and morning get_run

**Files:**
- Modify: `src/alphaloop/runtime/api.py`
- Modify: `tests/runtime/test_api.py`

**Interfaces:**
- `JobAPI.list_jobs() -> dict` with `{"jobs": [morning_view(...), ...]}` in store order
- `JobAPI.get_run` returns `morning_view` (superset of current `_job_dict` keys so existing tests still pass)
- `create_run` still adds `host_constraint`; `get_run` / `list_jobs` do not need to repeat it
- No method that accepts replacement hard gates or evidence

- [ ] Tests: list includes research_outcome first-class; get_run after writing gates.json returns FOUND + evidence; existing create/cancel/resume tests still pass
- [ ] Commit `feat(runtime): expose morning job list and evidence on Job API`

---

### Task 3: Daemon static root and job list HTTP

**Files:**
- Modify: `src/alphaloop/runtime/daemon.py`
- Modify: `src/alphaloop/runtime/client.py`
- Test: `tests/runtime/test_static_console.py`
- Modify: `tests/runtime/test_http.py`

**Interfaces:**
- `GET /` → `text/html` packaged `index.html` (not the old plaintext "alphaloop control plane")
- `GET /app.js`, `GET /styles.css` → packaged files, correct Content-Type
- Unknown static path under `/` that is not `/v1/...` or `/healthz` → 404
- `GET /v1/jobs` → JSON `{"jobs": [...]}`
- `JobClient.list_jobs()`
- `POST/PUT/PATCH /v1/jobs/{id}/gates` → 404 JSON `{"error": "not found"}` (no override)
- Path traversal (`/../`, encoded) must not escape the static root
- Serving uses `importlib.resources` of `alphaloop.webui.static`, not a Vite `dist/` that requires Node

- [ ] Tests: HTML content-type; list endpoint; gates override 404; healthz unchanged; create/get/cancel still work
- [ ] Commit `feat(runtime): serve packaged morning console and job list over HTTP`

---

### Task 4: Packaged morning console UI

**Files:**
- Create: `src/alphaloop/webui/static/__init__.py`
- Create: `src/alphaloop/webui/static/index.html`
- Create: `src/alphaloop/webui/static/app.js`
- Create: `src/alphaloop/webui/static/styles.css`

**Interfaces:**
- `index.html` contains a heading/landmark whose text or `data-outcome` attribute is filled by JS from `research_outcome`
- Page copy includes the three conclusion tokens as visible labels in the template or as rendered values
- On load, `GET /v1/jobs` and render a job list. Selecting a job `GET /v1/jobs/{id}` and show: outcome, stop_reason, evidence results, dominant_failures, revisions, queued_hypotheses
- No input that posts gate names, no "override", no "force FOUND"
- Tests read packaged files as text (no browser): HTML references `/app.js`; JS fetches `/v1/jobs`; strings `FOUND`, `NO_EVIDENCE`, `INCONCLUSIVE` present; JS does not contain `override` / `hard_gates=` assignment posts

- [ ] Commit `feat(webui): add packaged morning console static assets`

---

### Task 5: Docs, import graph, regression

**Files:**
- Modify: `docs/design/overnight-research-lab-refactor.md` Phase 4 → link this plan
- Modify: `docs/requirements/product-positioning-requirements.md` §13 — items 1–3 done; item 4 is this plan
- Modify: `docs/cli.md` — `alphaloop start` serves the morning console at `/`
- Modify: `tests/runtime/test_import_graph.py` — runtime may import `webui.static` resource path only; still no `alphaloop.live`; protocol still no webui/runtime
- Run: `python3 -m pytest tests/ -m "not integration" -q`

- [ ] Commit `docs: point Phase 4 morning Web at the implementation plan`

---

## Self-review

1. Spec coverage: packaged static (no Node), home leads with three outcomes, evidence + funnel + revisions + queued hypotheses, cannot override gates, daemon still loopback Job API.
2. Out of scope: Vite rewrite, `.asb` zip producer, Agent Skill, MCP, LLM planner, hosted cloud, changing diagnostic math.
3. Types: `morning_view` payload keys stay stable for Phase 6 Skill and a future richer SPA.
