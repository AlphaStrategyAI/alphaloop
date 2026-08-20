# Morning qualifying candidates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the frozen-grid points that passed every required hard gate on the morning payload, packaged console, and `report.md`.

**Architecture:** Add `build_qualifying_candidates` next to `build_funnel` using the same trial-file / last-`gates.json` fallback. `morning_view` copies the list. The static page renders `#qualifying` before evidence.

**Tech Stack:** Existing artifacts_io / morning / packaged console, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-qualifying-candidates.md`

## Global Constraints

- Do not promise alpha. Do not invent `FOUND`. No new hard gate.
- `HOST_CONSTRAINT` and help sentences stay locked. No `FakeWorker` in morning e2e.

---

### Task 1: Helper + morning_view + report

**Files:**
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Modify: `src/alphaloop/runtime/morning.py`
- Test: `tests/runtime/test_morning.py`
- Test: `tests/runtime/test_artifacts_io.py`

```python
def test_qualifying_candidates_from_passing_last_gates(tmp_path):
    ...  # existing test_passing_gates_found
    assert view["qualifying_candidates"] == [
        {"trial_id": "gates.json", "kind": None, "parameters": {}}
    ]

def test_failed_gate_has_empty_qualifying_candidates(...):
    assert view["qualifying_candidates"] == []

def test_qualifying_candidates_only_all_passed_trial_files(tmp_path):
    # c_pass all_passed, c_fail not → only c_pass with kind/parameters from ledger
```

Implement `build_qualifying_candidates(layout)` as specified. `write_report` adds `## Qualifying candidates`.

---

### Task 2: Console

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

HTML before Evidence:

```html
          <h3>Qualifying candidates</h3>
          <ul id="qualifying"></ul>
```

`showJob` `fillList(#qualifying, job.qualifying_candidates, ...)`.

E2E: after detail visible, `#qualifying` exists.
