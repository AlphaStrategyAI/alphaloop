# Verdict-cluster export receipt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `#export-status` sits in `#verdict` after `#handoff`, and a job switch clears a stale FOUND receipt.

**Architecture:** Move the existing node in `index.html`. `showJob` clears it only when `runId` changes so the two-second poll keeps a same-job receipt.

**Tech Stack:** Packaged static HTML/JS, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-verdict-export-receipt.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- No auto-export. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not change CLI export stdout.

---

### Task 1: Place + clear

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `docs/webui.md`, `mkdocs.yml`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Failing tests**

```python
assert html.find('id="handoff"') < html.find('id="export-status"')
assert html.find('id="export-status"') < html.find('id="job-status"')
assert "currentRunId !== runId" in script
```

E2E FOUND branch: wait on `#verdict #export-status`; first line `FOUND`.

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_asb_export -v
```

- [ ] **Step 3: Implement**

Move `<p id="export-status"></p>` into `#verdict` after `#handoff`.
`showJob`: clear status when `currentRunId !== runId`. Docs.

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(webui): show the export receipt in the morning verdict"
```
