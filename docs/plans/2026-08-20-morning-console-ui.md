# Morning console UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the packaged morning page load an example spec, cancel/resume from the detail pane, and scan as a two-column overnight console without changing research semantics.

**Architecture:** Static HTML/CSS/JS only. Example YAML is a JS constant. Cancel/resume POST existing Job API paths. Layout wrappers `#before-bed` and `#morning`. Job list `textContent` format stays.

**Tech Stack:** Packaged static assets, existing Job API, pytest, Playwright.

## Global Constraints

- Local-first overnight lab. Do not promise alpha. Do not invent `FOUND`.
- No `FakeWorker` in morning e2e. Frozen Vite SPA. No webfont fetch.
- List button text remains `{run_id} — {status} — {research_outcome}`.
- Use `python3`.

---

### Task 1: Example spec + layout wrappers + cancel/resume markup

**Files:** `src/alphaloop/webui/static/index.html`, `app.js`, `styles.css`
**Test:** `tests/runtime/test_static_console.py`

- [ ] **Step 1: Failing tests** — assert `#load-example`, `#before-bed`, `#morning`, `#cancel-job`, `#resume-job`, example `statement: 12-1 momentum`, `/cancel`, `/resume` in JS, list format string unchanged.

- [ ] **Step 2:** Run; expect fail.

- [ ] **Step 3:** Implement.

HTML: wrap submit in `<section id="before-bed">`, wrap jobs+detail in `<section id="morning">`. Add `#load-example`. In detail, add:

```html
<p>
  <button id="cancel-job" type="button" hidden>Cancel</button>
  <button id="resume-job" type="button" hidden>Resume</button>
</p>
```

JS `EXAMPLE_SPEC` constant (README YAML + trailing newline). `load-example` sets textarea value and dispatches `input`.

`showJob` stores `currentRunId`. Cancel: `POST /v1/jobs/{id}/cancel`. Resume: `POST /v1/jobs/{id}/resume`. Then `showJob` + `loadJobs`.

Visibility: cancel if status in `queued`,`running`; resume if `failed`.

`loadJobs` sets `button.dataset.status` and `button.dataset.outcome`.

`styles.css`: two-column `#console` grid at `min-width: 56rem`; system-ui + ui-monospace; cards; focus-visible; job button left border from `data-outcome`.

- [ ] **Step 4:** Static tests pass. Commit.

---

### Task 2: E2E + docs

**Files:** `tests/e2e/test_morning_console.py`, `docs/webui.md`, `mkdocs.yml`

- [ ] Load-example fills textarea with the statement line; submit still disabled; no job row.
- [ ] After preview+submit of a long-budget job, open detail, click `#cancel-job`, list outcome `INCONCLUSIVE` or status cancelled with inconclusive research outcome.
- [ ] Update `docs/webui.md` lead. Register req/plan in `mkdocs.yml`.

Keep `_list_research_outcome` as last ` — ` segment.

- [ ] `python3 -m pytest -m "not e2e and not llm"` then e2e. Commit.
