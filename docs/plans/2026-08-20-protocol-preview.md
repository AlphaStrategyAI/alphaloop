# Protocol preview before freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the morning console show the compiled research protocol (grid, planned trials, spec_id) and freeze it only after a successful preview, without starting a worker on preview.

**Architecture:** `JobAPI.preview_run` is preflight plus `method_parameter_grid`, no `store.create`. `POST /v1/jobs/preview` returns that dict. The packaged page previews first; `#submit-job` stays disabled until the current YAML previewed with `ok: true`.

**Tech Stack:** Existing Job API, stdlib HTTP daemon, packaged HTML/JS, pytest, Playwright.

## Global Constraints

- Local-first overnight lab. Do not promise alpha. Do not invent `FOUND`.
- No `FakeWorker` in morning e2e. Frozen `alphaloop.live`.
- `alphaloop.protocol` must not import `runtime`. Runtime may import protocol.
- Use `python3`.

---

### Task 1: `preview_run`

**Files:**
- Modify: `src/alphaloop/runtime/api.py`
- Test: `tests/runtime/test_api.py`

- [ ] **Step 1: Failing test** in `tests/runtime/test_api.py`:

```python
from alphaloop.protocol.search import method_parameter_grid


def test_preview_run_does_not_create_a_job(tmp_path):
    api = _api(tmp_path)
    spec = _spec()
    preview = api.preview_run(spec)
    assert preview["ok"] is True
    assert preview["spec_id"] == spec.spec_id
    assert preview["signal_mechanism"] == spec.hypothesis.signal_mechanism
    assert preview["planned_n_trials"] == len(
        method_parameter_grid(spec.hypothesis.signal_mechanism)
    )
    assert preview["method_parameter_grid"] == list(
        method_parameter_grid(spec.hypothesis.signal_mechanism)
    )
    assert "run_id" not in preview
    assert api.list_jobs()["jobs"] == []


def test_preview_run_preflight_failure_is_not_ok(tmp_path):
    api = _api(tmp_path)
    spec = _spec()
    object.__setattr__(spec.success_criteria, "hard_gates", ())
    preview = api.preview_run(spec)
    assert preview["ok"] is False
    assert preview["errors"]
    assert api.list_jobs()["jobs"] == []
```

Use whatever `_api` / `_spec` helpers already exist in that file. If `success_criteria` is frozen, build a spec with `hard_gates=()` via `new_research_spec` instead.

- [ ] **Step 2:** Run the tests; expect `AttributeError: preview_run`.
- [ ] **Step 3:** Implement `JobAPI.preview_run`.
- [ ] **Step 4:** Tests pass. Commit.

---

### Task 2: HTTP `POST /v1/jobs/preview`

**Files:**
- Modify: `src/alphaloop/runtime/daemon.py`
- Test: `tests/runtime/test_http.py`

Route `POST /v1/jobs/preview` **before** treating extra path segments as cancel/resume. Parse body like `_create_run`. 200 + preview dict. 400 on parse error. No `run_id`.

- [ ] Tests: YAML preview 200, list empty; bad YAML 400.
- [ ] Commit.

---

### Task 3: Packaged page

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`, `app.js`
- Test: `tests/runtime/test_static_console.py`

HTML: `#preview-protocol`, `#protocol-preview`. `#submit-job` starts `disabled`.

JS: preview POSTs `/v1/jobs/preview`. On `ok`, fill `#protocol-preview` with `spec_id`, `planned_n_trials`, JSON grid, enable submit, remember textarea snapshot. On textarea `input`, disable submit. Submit still POSTs `/v1/jobs`.

- [ ] Tests assert ids, `/v1/jobs/preview` in JS, `disabled` on submit.
- [ ] Commit.

---

### Task 4: E2E + docs

**Files:**
- Modify: `tests/e2e/test_morning_console.py`, `docs/webui.md`, `mkdocs.yml`

Helper `_preview_then_submit(page, yaml_text)`: fill, click preview, wait for `#protocol-preview` to contain `planned_n_trials`, click submit.

Replace `page.fill` + `page.click("#submit-job")` sequences that intend to create a job with the helper. Invalid YAML test clicks preview instead.

New tests:

- Preview does not add a job-list button.
- After preview, editing textarea leaves submit disabled (check `disabled` property).

`docs/webui.md` lead: preview then freeze.

- [ ] `python3 -m pytest -m "not e2e and not llm"` then `python3 -m pytest tests/e2e -m e2e`
- [ ] Commit.
