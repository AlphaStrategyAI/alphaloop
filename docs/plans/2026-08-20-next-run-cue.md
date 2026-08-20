# Morning next-run cue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the first queued follow-up inside the morning verdict so a five-minute reader can load the next constrained run without scrolling.

**Architecture:** `#next-step` is a view of `queued_hypotheses[0]`. The existing `loadQueuedHypothesis` path stays the only editor fill. Empty queue → empty node.

**Tech Stack:** Packaged static console, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-next-run-cue.md`

## Global Constraints

- Do not invent `FOUND`. Do not auto-submit. Do not change `HOST_CONSTRAINT` or Help sentences.
- No `FakeWorker` in morning e2e. Do not unfreeze `webui/`.

---

### Task 1: Verdict next-run cue

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Write the failing tests**

In `test_packaged_console_morning_verdict_stage`:

```python
assert html.find('id="stop-reason"') < html.find('id="next-step"')
assert html.find('id="next-step"') < html.find('id="job-status"')
assert "fillNextStep" in script
assert "Next run:" in script
```

In `test_load_queued_fills_editor_without_submitting`, wait for
`#next-step button.load-queued` and click that button instead of
`#queued button.load-queued`. Keep the rsi / single-job assertions.

- [ ] **Step 2: Run the static test to verify it fails**

Run: `python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_morning_verdict_stage -v`

Expected: FAIL (`id="next-step"` missing).

- [ ] **Step 3: Implement**

HTML: `<div id="next-step"></div>` inside `#verdict` after `#stop-reason`.

```javascript
function fillNextStep(job) {
  const node = document.getElementById("next-step");
  node.innerHTML = "";
  const items = job.queued_hypotheses || [];
  if (!items.length) {
    return;
  }
  const row = items[0];
  const text = document.createElement("span");
  text.textContent = "Next run: " + (row.statement || "");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "load-queued";
  button.textContent = "Load into editor";
  button.addEventListener("click", function () {
    loadQueuedHypothesis(row, job);
  });
  node.appendChild(text);
  node.appendChild(button);
}
```

Call `fillNextStep(job)` from `showJob` after `fillPrimaryEvidence`.
Style `#next-step` as a row in the verdict (flex, gap). No `http` in CSS.

- [ ] **Step 4: Run unit then e2e**

```bash
python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration
python3 -m pytest tests/e2e -m e2e
```

- [ ] **Step 5: Commit**
