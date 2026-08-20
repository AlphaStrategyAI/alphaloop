# Morning FOUND handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the first sealed qualifying candidate inside the morning verdict on `FOUND`, with the same human-triggered `.asb` export lock as `#qualifying`.

**Architecture:** `#handoff` is a view of `qualifying_candidates[0]` only when `research_outcome` is `FOUND`. `exportCandidate` stays the only writer. Other outcomes leave the node empty.

**Tech Stack:** Packaged static console, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-found-handoff.md`

## Global Constraints

- Do not invent `FOUND`. Do not auto-export. Do not change `HOST_CONSTRAINT` or Help sentences.
- No `FakeWorker` in morning e2e. Do not unfreeze `webui/`.
- `gates.json` trial ids are not exportable.

---

### Task 1: Verdict FOUND handoff

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Write the failing tests**

In `test_packaged_console_morning_verdict_stage`:

```python
assert html.find('id="next-step"') < html.find('id="handoff"')
assert html.find('id="handoff"') < html.find('id="job-status"')
assert "fillHandoff" in script
assert "Qualifying:" in script
```

In `test_export_found_only`, when `outcome == "FOUND"`, click
`#verdict #handoff button.export-asb` instead of
`#qualifying button.export-asb`. When not `FOUND`, assert
`page.locator("#handoff button.export-asb").count() == 0`.

- [ ] **Step 2: Run the static test to verify it fails**

Run: `python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_morning_verdict_stage -v`

Expected: FAIL (`id="handoff"` missing).

- [ ] **Step 3: Implement**

HTML: `<div id="handoff"></div>` inside `#verdict` after `#next-step`.

```javascript
function fillHandoff(job) {
  const node = document.getElementById("handoff");
  node.innerHTML = "";
  const rows = job.qualifying_candidates || [];
  if (job.research_outcome !== "FOUND" || !rows.length) {
    return;
  }
  const row = rows[0];
  const trial = row.trial_id || "gates.json";
  const text = document.createElement("span");
  text.textContent =
    "Qualifying: " +
    trial +
    " · " +
    (row.kind || "") +
    " · " +
    formatGridRow(row.parameters);
  node.appendChild(text);
  if (trial.indexOf("c_") === 0) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "export-asb";
    button.textContent = "Export .asb";
    button.addEventListener("click", function () {
      exportCandidate(trial);
    });
    node.appendChild(button);
  }
}
```

Call `fillHandoff(job)` from `showJob` after `fillNextStep`.
Reuse `#next-step` flex styling on `#handoff`. No `http` in CSS.

- [ ] **Step 4: Run unit then e2e**

```bash
python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration
python3 -m pytest tests/e2e -m e2e
```

- [ ] **Step 5: Commit**
