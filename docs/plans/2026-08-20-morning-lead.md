# Morning home leads with the latest job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open the latest overnight job on the morning home page, list newest first, refresh the open detail on the existing poll, and show a mini funnel on each job card.

**Architecture:** Reverse `list_jobs` SQL. Teach `loadJobs` to select the latest id and call `showJob`. Extract `fillFunnelStack` for `#funnel-bars` and `.job-funnel`.

**Tech Stack:** SQLite job store, packaged static console, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-morning-lead.md`

## Global Constraints

- Do not promise alpha. Do not invent `FOUND`. No new hard gate.
- `HOST_CONSTRAINT` and help sentences stay locked. No `FakeWorker` in morning e2e.
- Do not unfreeze the Vite SPA under `webui/`.

---

### Task 1: Newest-first `list_jobs`

**Files:**
- Modify: `src/alphaloop/runtime/store.py`
- Test: `tests/runtime/test_store.py`

```python
def test_list_jobs_newest_first(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    first = store.create(_spec())
    second = store.create(_spec())
    ids = [job.run_id for job in store.list_jobs()]
    assert ids == [second.run_id, first.run_id]
```

Change SQL to `ORDER BY created_at DESC, run_id DESC`.

---

### Task 2: Auto-open, live detail, mini-funnel

**Files:**
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

Extract:

```javascript
function fillFunnelStack(host, funnel) {
  host.innerHTML = "";
  const evaluated = funnel.n_evaluated || 0;
  const passed = funnel.n_passed || 0;
  const failed = funnel.n_failed || 0;
  const incomplete = funnel.n_incomplete || 0;
  if (evaluated + passed + failed + incomplete <= 0) {
    return;
  }
  const stack = document.createElement("div");
  stack.className = "funnel-stack";
  const whole = evaluated > 0 ? evaluated : passed + failed + incomplete;
  appendFunnelSeg(stack, "passed", passed, whole);
  appendFunnelSeg(stack, "failed", failed, whole);
  appendFunnelSeg(stack, "incomplete", incomplete, whole);
  host.appendChild(stack);
}
```

`fillFunnel` uses `fillFunnelStack(bars, funnel)`.

`loadJobs`: after rendering, if `!currentRunId` or id not in list, set to `jobs[0].run_id` or null; if set, `await showJob(currentRunId)`; else hide `#detail`. Each card gets `.job-funnel` + `fillFunnelStack`, and `aria-current` when selected.

`submitJob`: `currentRunId = body.run_id` then `await loadJobs()`.

CSS:

```css
.job-funnel .funnel-stack {
  height: 0.45rem;
  margin: 0.4rem 0 0;
}
#job-list button[aria-current="true"] {
  border-color: var(--focus);
}
```

Tests: packaged `job-funnel`, `aria-current`, `fillFunnelStack`; e2e empty home `#detail` hidden; after submit detail visible; terminal card has `.job-funnel .funnel-stack`.
