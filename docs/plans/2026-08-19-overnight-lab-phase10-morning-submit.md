# Overnight Lab Phase 10 — Morning Submit, Preflight, and Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user submit a frozen hypothesis from the packaged morning page in one minute, see preflight errors (including the locked host constraint), and watch job progress without Node, without overriding gates, and without leaving loopback.

**Architecture:** Phase 4 already serves vanilla HTML/JS that lists jobs and renders sealed evidence. `POST /v1/jobs` already exists. Phase 10 adds `spec_from_submit_payload` so a YAML textarea does not need a precomputed `spec_id`, accepts `application/yaml` on the daemon, shows existing preflight `errors` in the page, and polls `GET /v1/jobs` while a job is `queued`/`running`. Dataset hash checks stay in Phase 9. No Vite, no FastAPI on this path, no PATCH of `hard_gates`.

**Tech Stack:** Python 3.9+, stdlib `http.server`, PyYAML (existing), vanilla HTML/JS/CSS, pytest, Phase 2 Job API.

## Global Constraints

- Home page leads with `FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE` (or `NONE` while running). Copy must use those exact tokens.
- Web console cannot override evidence gates. No PATCH/PUT/POST that mutates `GateEvidence` or `success_criteria.hard_gates`.
- End users do not install Node. Assets stay packaged in `alphaloop.webui.static`.
- Bind remains loopback (`127.0.0.1`) by default.
- Do not import `alphaloop.live`. Do not import FastAPI `alphaloop.webui.api` from `runtime/`.
- `alphaloop.protocol` must not import `webui` or `runtime`.
- `FOUND` is display-only of sealed evidence; the UI cannot mint it.
- Preflight always returns locked `HOST_CONSTRAINT` text.
- Tests use the Job API / HTTP daemon; no network; no browser driver.
- Source of truth: `docs/requirements/product-positioning-requirements.md` §4.3 / §10.1 and `docs/plans/2026-08-19-overnight-lab-remaining-work.md`.

## File Structure

- Create: `src/alphaloop/runtime/submit.py` — `spec_from_submit_payload`
- Modify: `src/alphaloop/runtime/daemon.py` — YAML POST body; use submit helper
- Modify: `src/alphaloop/runtime/api.py` — optional: create_run still takes `ResearchSpec`
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css` (minimal submit form spacing only)
- Modify: `src/alphaloop/skills/overnight-lab/SKILL.md` — mention Web submit + poll
- Test: `tests/runtime/test_submit.py`
- Test: `tests/runtime/test_http.py`
- Test: `tests/runtime/test_static_console.py`

## Out of scope (later plans)

- Protocol return math, checkpoint resume, parquet writers (Phases 8–9)
- CI pytest workflow (Phase 11)
- Remote bind, auth, multi-user
- Rich spec builder UI, ticker pickers, gate checkboxes

---

### Task 1: Accept submit payloads without `spec_id`

**Files:**
- Create: `src/alphaloop/runtime/submit.py`
- Modify: `src/alphaloop/runtime/daemon.py`
- Test: `tests/runtime/test_submit.py`
- Test: `tests/runtime/test_http.py`

**Interfaces:**
- Consumes: mapping from JSON or YAML
- Produces: `spec_from_submit_payload(payload: Mapping[str, Any]) -> ResearchSpec`
  - If `payload` already has `spec_id`, `hypothesis`, `success_criteria`, `seed`, `time_budget_s`, `cost_budget_usd` → `ResearchSpec.from_dict(payload)` (existing strict hash check)
  - Else require keys `statement`, `economic_logic`, `signal_mechanism`, `market_scope`, `market_profile`, `benchmark`, `hard_gates`, `seed`, `time_budget_s`, `cost_budget_usd` at the **top level** OR nested as today under `hypothesis` / `success_criteria` without `spec_id`
  - Nested form without `spec_id`: `new_research_spec(statement=hyp["statement"], ..., hard_gates=crit["hard_gates"], seed=..., time_budget_s=..., cost_budget_usd=..., dataset=...)`
  - Optional `dataset` mapping `{dataset_id, sha256}` forwarded to `new_research_spec`
  - Invalid → `ValueError` with a short message (daemon already maps `ValueError` to 400 `{"error": ...}`)

- [ ] **Step 1: Write the failing tests**

Create `tests/runtime/test_submit.py`:

```python
from __future__ import annotations

import pytest

from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.runtime.submit import spec_from_submit_payload
from tests.runtime.test_supervisor import _spec


def test_full_spec_dict_round_trips():
    spec = _spec()
    assert spec_from_submit_payload(spec.to_dict()) == spec


def test_nested_payload_without_spec_id_builds_research_spec():
    spec = _spec()
    payload = spec.to_dict()
    payload.pop("spec_id")
    built = spec_from_submit_payload(payload)
    assert built == spec
    assert built.spec_id == spec.spec_id


def test_flat_payload_without_spec_id_builds_research_spec():
    spec = _spec()
    payload = {
        "statement": spec.hypothesis.statement,
        "economic_logic": spec.hypothesis.economic_logic,
        "signal_mechanism": spec.hypothesis.signal_mechanism,
        "market_scope": spec.hypothesis.market_scope,
        "market_profile": spec.hypothesis.market_profile,
        "benchmark": spec.hypothesis.benchmark,
        "hard_gates": list(spec.success_criteria.hard_gates),
        "seed": spec.seed,
        "time_budget_s": spec.time_budget_s,
        "cost_budget_usd": spec.cost_budget_usd,
    }
    built = spec_from_submit_payload(payload)
    assert built.spec_id == spec.spec_id


def test_wrong_spec_id_still_rejected():
    payload = _spec().to_dict()
    payload["spec_id"] = "rs_" + "0" * 32
    with pytest.raises(ValueError, match="spec_id"):
        spec_from_submit_payload(payload)
```

Add to `tests/runtime/test_http.py`:

```python
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def test_http_create_accepts_payload_without_spec_id(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, heartbeat_timeout_s=60.0)
    api = JobAPI(store, sup, tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    try:
        payload = _spec().to_dict()
        payload.pop("spec_id")
        req = Request(
            f"http://{host}:{port}/v1/jobs",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req) as response:
            body = json.loads(response.read().decode("utf-8"))
            assert response.status == 201
            assert body["run_id"].startswith("j_")
            assert body["host_constraint"]
    finally:
        server.shutdown()
```

- [ ] **Step 2: Run the new tests, expect FAIL**

Run:

```
python -m pytest tests/runtime/test_submit.py tests/runtime/test_http.py::test_http_create_accepts_payload_without_spec_id -v
```

Expected: FAIL (`ModuleNotFoundError: alphaloop.runtime.submit`) and/or HTTP 400 `spec_id`.

- [ ] **Step 3: Write minimal implementation**

`spec_from_submit_payload`:

```python
def spec_from_submit_payload(payload: Mapping[str, Any]) -> ResearchSpec:
    if not isinstance(payload, Mapping):
        raise ValueError("research spec must be a mapping")
    if "spec_id" in payload:
        return ResearchSpec.from_dict(payload)
    if "hypothesis" in payload:
        hyp = payload["hypothesis"]
        crit = payload["success_criteria"]
        return new_research_spec(
            statement=str(hyp["statement"]),
            economic_logic=str(hyp["economic_logic"]),
            signal_mechanism=str(hyp["signal_mechanism"]),
            market_scope=str(hyp["market_scope"]),
            market_profile=str(hyp["market_profile"]),
            benchmark=str(hyp["benchmark"]),
            hard_gates=tuple(crit["hard_gates"]),
            seed=int(payload["seed"]),
            time_budget_s=int(payload["time_budget_s"]),
            cost_budget_usd=float(payload["cost_budget_usd"]),
            dataset=_optional_dataset(payload.get("dataset")),
        )
    return new_research_spec(
        statement=str(payload["statement"]),
        ...
        dataset=_optional_dataset(payload.get("dataset")),
    )
```

Parse optional `dataset` the same way `ResearchSpec.from_dict` does after Phase 9 (`DatasetRef` or `None`) and pass it to `new_research_spec(..., dataset=...)`.

In `daemon.py` `_create_run`, replace `ResearchSpec.from_dict(payload)` with `spec_from_submit_payload(payload)`.

- [ ] **Step 4: Run submit + HTTP tests, expect PASS**

Run: `python -m pytest tests/runtime/test_submit.py tests/runtime/test_http.py tests/runtime/test_api.py -v`

Expected: PASS. Existing `client.create_run(_spec())` still works.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/submit.py src/alphaloop/runtime/daemon.py tests/runtime/test_submit.py tests/runtime/test_http.py
git commit -m "feat(runtime): accept research specs without a precomputed spec_id"
```

---

### Task 2: YAML POST body

**Files:**
- Modify: `src/alphaloop/runtime/daemon.py`
- Test: `tests/runtime/test_http.py`

**Interfaces:**
- Consumes: POST body bytes + `Content-Type`
- Produces: if `Content-Type` starts with `application/yaml` or `text/yaml` (ignore charset suffix), `yaml.safe_load` the body; otherwise JSON as today. Loaded value must be a `dict` or raise `ValueError`. Then `spec_from_submit_payload`. Dataset hash checks stay in Phase 9 `preflight`.

- [ ] **Step 1: Write the failing test**

Add `import json` and `import yaml` to `tests/runtime/test_http.py` if missing, then:

```python
def test_http_create_accepts_yaml_body(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    try:
        payload = _spec().to_dict()
        payload.pop("spec_id")
        req = Request(
            f"http://{host}:{port}/v1/jobs",
            data=yaml.safe_dump(payload).encode("utf-8"),
            headers={"Content-Type": "application/yaml"},
            method="POST",
        )
        with urlopen(req) as response:
            assert response.status == 201
            body = json.loads(response.read().decode("utf-8"))
            assert "run_id" in body
    finally:
        server.shutdown()
```

- [ ] **Step 2: Run the new test, expect FAIL**

Run: `python -m pytest tests/runtime/test_http.py::test_http_create_accepts_yaml_body -v`

Expected: FAIL (YAML body parsed as JSON → 400).

- [ ] **Step 3: Write minimal implementation**

In `_read_json` or a new `_read_payload`, branch on `self.headers.get("Content-Type", "")`. `yaml.safe_load` must return a `dict` or raise `ValueError`. Keep JSON for `application/json` and missing content type.

- [ ] **Step 4: Run HTTP tests, expect PASS**

Run: `python -m pytest tests/runtime/test_http.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/daemon.py tests/runtime/test_http.py
git commit -m "feat(runtime): accept YAML bodies on POST /v1/jobs"
```

---

### Task 3: Packaged submit form and progress poll

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Test: `tests/runtime/test_static_console.py`

**Interfaces:**
- Consumes: existing `GET /v1/jobs`, `POST /v1/jobs`, `GET /v1/jobs/{id}`
- Produces: morning page with
  - `<textarea id="spec-yaml">` and `<button id="submit-job" type="button">Submit</button>`
  - `<p id="preflight-errors">` for 400 `errors` joined by `; ` or JSON `error`
  - `<p id="host-constraint">` filled from create response `host_constraint` (or left empty until submit)
  - `loadJobs()` called on load **and** every 2000 ms via `setInterval`
  - Submit: `fetch("/v1/jobs", {method:"POST", headers:{"Content-Type":"application/yaml"}, body: textarea.value})`
  - On 201: clear preflight errors, show host constraint, `loadJobs()`
  - On 400: show `errors` list; do not mint an outcome
  - Still no string `override`, no `hard_gates=` mutation
  - Job list buttons still open the review pane

- [ ] **Step 1: Write the failing tests**

Update `test_packaged_assets_are_read_only_morning_copy` in `tests/runtime/test_static_console.py` (keep existing assertions; add):

```python
    assert 'id="spec-yaml"' in html
    assert 'id="submit-job"' in html
    assert "application/yaml" in script
    assert "setInterval" in script
    assert "/v1/jobs" in script
```

Add a daemon-level test that the HTML at `/` includes the textarea (existing `test_root_serves_packaged_html` can assert `spec-yaml` in body).

- [ ] **Step 2: Run the new assertions, expect FAIL**

Run: `python -m pytest tests/runtime/test_static_console.py::test_packaged_assets_are_read_only_morning_copy -v`

Expected: FAIL (`id="spec-yaml"` not in html).

- [ ] **Step 3: Write minimal implementation**

In `index.html`, **before** `<section id="jobs">`:

```html
      <section id="submit">
        <h2>Submit</h2>
        <label for="spec-yaml">Research spec (YAML)</label>
        <textarea id="spec-yaml" rows="16" cols="72"></textarea>
        <p>
          <button id="submit-job" type="button">Submit</button>
        </p>
        <p id="preflight-errors"></p>
        <p id="host-constraint"></p>
      </section>
```

In `app.js`, add:

```javascript
async function submitJob() {
  const errors = document.getElementById("preflight-errors");
  const constraint = document.getElementById("host-constraint");
  errors.textContent = "";
  const response = await fetch("/v1/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/yaml" },
    body: document.getElementById("spec-yaml").value,
  });
  const body = await response.json();
  if (!response.ok) {
    const list = body.errors || [body.error || "submit failed"];
    errors.textContent = list.join("; ");
    return;
  }
  if (body.host_constraint) {
    constraint.textContent = body.host_constraint;
  }
  loadJobs();
}

document.getElementById("submit-job").addEventListener("click", function () {
  submitJob();
});

setInterval(loadJobs, 2000);
```

Keep the trailing `loadJobs();`. Do not add gate override controls. CSS: make `textarea` `width: 100%; font-family: monospace`.

- [ ] **Step 4: Run static console tests, expect PASS**

Run: `python -m pytest tests/runtime/test_static_console.py -v`

Expected: PASS. `test_static_package_loads_without_fastapi` still passes.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/webui/static/index.html src/alphaloop/webui/static/app.js src/alphaloop/webui/static/styles.css tests/runtime/test_static_console.py
git commit -m "feat(webui): submit YAML jobs and poll morning progress"
```

---

### Task 4: Skill + docs pointers

**Files:**
- Modify: `src/alphaloop/skills/overnight-lab/SKILL.md`
- Modify: `docs/cli.md` only if the morning page sentence is still “review only”
- Test: `tests/skills/test_overnight_lab_skill.py` (if it snapshots Skill text, update the expected phrases)

**Interfaces:**
- Skill workflow step: user may submit via morning `/` YAML box **or** `alphaloop submit --spec PATH`. Poll the page or `alphaloop status`. Disclose `HOST_CONSTRAINT`.

- [ ] **Step 1: Write / adjust the skill test**

If `tests/skills/test_overnight_lab_skill.py` asserts substrings, add:

```python
assert "Submit" in text or "YAML" in text
```

Keep “Do not claim alpha” and host-constraint lock.

- [ ] **Step 2: Run, expect FAIL if copy missing**

Run: `python -m pytest tests/skills/test_overnight_lab_skill.py -v`

- [ ] **Step 3: Update Skill.md workflow** with one sentence: the packaged morning page can POST YAML to `/v1/jobs` and polls every two seconds; it cannot change hard gates.

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/skills/overnight-lab/SKILL.md tests/skills/test_overnight_lab_skill.py docs/cli.md
git commit -m "docs(skill): mention morning YAML submit and progress poll"
```
