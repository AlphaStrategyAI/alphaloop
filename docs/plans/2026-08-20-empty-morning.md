# Empty morning cue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a first-run morning empty state that names Load example → Preview → Freeze, and stop ROADMAP from listing shipped work as unfinished.

**Architecture:** `#empty-morning` visibility follows `jobs.length`. ROADMAP remaining list matches current `main`.

**Tech Stack:** Packaged static console, pytest, Playwright.

**Spec:** `docs/requirements/2026-08-20-empty-morning.md`

## Global Constraints

- Do not invent `FOUND` or a job. Do not change Help / `HOST_CONSTRAINT`.
- No FakeWorker in morning e2e.

---

### Task 1: Empty cue + ROADMAP honesty

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`, `app.js`, `styles.css`
- Modify: `ROADMAP.md`
- Test: `tests/runtime/test_static_console.py`, `tests/e2e/test_morning_console.py`

- [x] **Step 1: Failing tests**

Static: `id="empty-morning"` after `job-list`; locked sentence in HTML; `empty-morning` / `.hidden` in script.

E2E `test_home_shows_promise_and_submit_form`: `#empty-morning` visible with locked sentence.

E2E after submit (e.g. `test_preview_then_submit` or job card test): `#empty-morning` hidden.

- [x] **Step 2: FAIL then implement**

- [x] **Step 3: ROADMAP remaining = soak execution, \(N_{\mathrm{eff}}\), later MCP/cloud**

- [ ] **Step 4: Unit + e2e**

- [ ] **Step 5: Commit**
