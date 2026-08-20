# Preview protocol designed chrome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Packaged `#preview-protocol` uses designed focus-blue chrome, not FOUND green.

**Architecture:** CSS only. `--ink` background, `--focus` border/text, Freeze-sized padding. `#submit-job` unchanged.

**Tech Stack:** packaged `styles.css`, pytest static + Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-preview-chrome.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not auto-submit. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not restyle Freeze.

---

### Task 1: Designed chrome

**Files:**
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`, `mkdocs.yml`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Failing tests**

Static: `#preview-protocol {` block has `var(--ink)`, `var(--focus)`, not `var(--accent)`.

E2E: `test_home_shows_promise_and_submit_form` waits until `#preview-protocol` color is `rgb(126, 184, 255)` and background is `rgb(11, 15, 22)`.

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_preview_chrome -v
```

- [ ] **Step 3: Implement**

Add `#preview-protocol` chrome with `--ink` / `--focus`. Leave `#submit-job` alone.

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(webui): style Preview protocol as a before-bed control"
```
