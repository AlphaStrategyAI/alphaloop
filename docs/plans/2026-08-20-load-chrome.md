# Load example designed chrome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Packaged `#load-example` uses designed secondary chrome, not FOUND green.

**Architecture:** CSS only. `--ink` background, `--fg` / `--line`, Freeze-sized padding. Preview and Freeze unchanged.

**Tech Stack:** packaged `styles.css`, pytest static + Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-load-chrome.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not auto-submit. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not restyle Preview or Freeze.

---

### Task 1: Designed chrome

**Files:**
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`, `mkdocs.yml`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [x] **Step 1: Failing tests**

Static: `#load-example {` has `var(--ink)`, `var(--fg)`, `var(--line)`; not `--accent` / `--warn` / `--focus`.

E2E: home waits until `#load-example` background is `rgb(11, 15, 22)` and color is `rgb(243, 239, 230)`.

- [x] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_load_chrome -v
```

- [x] **Step 3: Implement**

Add `#load-example` chrome. Leave `#preview-protocol` and `#submit-job` alone.

- [x] **Step 4: Tests pass**

- [x] **Step 5: Commit**

```bash
git commit -m "feat(webui): style Load example as a before-bed control"
```
