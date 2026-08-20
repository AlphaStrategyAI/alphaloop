# Lifecycle Cancel/Resume above the report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the one `.actions` node (Cancel / Resume) above `#report`, after `#recovery-attempts`.

**Architecture:** HTML reorder only. `showJob` hide/show stays. Existing e2e cancel click keeps working.

**Tech Stack:** Packaged static HTML, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-lifecycle-actions.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change cancel/resume hide rules or CLI stdout. No FakeWorker in morning e2e.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.

---

### Task 1: Place actions

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `docs/webui.md`, `mkdocs.yml`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py` (existing cancel e2e still passes)

- [ ] **Step 1: Failing tests**

```python
assert html.find('id="recovery-attempts"') < html.find('id="cancel-job"')
assert html.find('id="cancel-job"') < html.find('id="resume-job"')
assert html.find('id="resume-job"') < html.find('id="report"')
assert html.find('id="report"') < html.find('id="qualifying"')
```

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_morning_report -v
```

- [ ] **Step 3: Implement**

Move `p.actions` to after `#recovery-attempts` and before `#hypothesis-statement`.

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(webui): put Cancel and Resume above the morning report"
```
