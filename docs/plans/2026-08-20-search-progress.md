# Overnight search progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show frozen-grid search progress (`n_trials / planned_n_trials`) on the packaged job list and detail so an overnight wait is visible without implying alpha.

**Architecture:** Copy preview's `len(method_parameter_grid)` onto `morning_view`. Render a `.search-progress` bar from that payload. No protocol change.

**Tech Stack:** `alphaloop.runtime.morning`, packaged static console, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-search-progress.md`

## Global Constraints

- Do not promise alpha. Do not invent `FOUND`. No new hard gate.
- `HOST_CONSTRAINT` and help sentences stay locked. No `FakeWorker` in morning e2e.
- Do not unfreeze the Vite SPA under `webui/`.

---

### Task 1: `planned_n_trials` + console bar

**Files:**
- Modify: `src/alphaloop/runtime/morning.py`
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Test: `tests/runtime/test_morning.py`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Failing tests**

```python
def test_morning_view_exposes_planned_n_trials(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    view = morning_view(store.get(job.run_id), tmp_path)
    assert view["planned_n_trials"] == 3
    assert view["n_trials"] == 0
```

Packaged:

```python
def test_packaged_search_progress():
    ...
    assert "search: " in script
    assert "search-progress-fill" in script
    assert ".search-progress" in css
    assert 'id="search-progress"' in html
```

E2E `test_job_card_shows_hypothesis_and_n_trials`:

```python
    assert "search:" in card.inner_text()
    assert "/ 3" in card.inner_text() or "/3" in card.inner_text()
```

E2E job detail:

```python
    assert "planned_n_trials:" in meta
    page.locator("#search-progress .search-progress-fill").get_attribute("data-pct")
```

- [ ] **Step 2: Run morning test — expect FAIL on missing key.**

- [ ] **Step 3: Implement**

`morning.py`:

```python
from alphaloop.protocol.search import method_parameter_grid
...
"planned_n_trials": len(method_parameter_grid(job.spec.hypothesis.signal_mechanism)),
```

`index.html` after `#spec-meta`:

```html
          <div id="search-progress"></div>
```

`app.js` helper `fillSearchProgress(host, n, planned)` sets track+fill; call from `loadJobs` and `showJob`.

- [ ] **Step 4:** unit then e2e.
- [ ] **Step 5: Commit**
