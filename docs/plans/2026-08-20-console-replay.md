# Console Replay report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Packaged **Replay report** rewrites `report.md` from sealed artifacts without inventing `FOUND`.

**Architecture:** Shared `rewrite_sealed_report`. `POST /v1/jobs/{id}/replay` returns `morning_view`. Console `#replay-job` in `.actions` above `#report`. CLI stdout unchanged.

**Tech Stack:** JobAPI, daemon POST, packaged static JS/CSS, pytest, Playwright.

**Spec:** `docs/requirements/2026-08-20-console-replay.md`

## Global Constraints

- Do not invent `FOUND`. Do not re-run gates. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change CLI replay stdout. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs.

---

### Task 1: API + console button

**Files:**
- Create: `src/alphaloop/runtime/replay.py` (shared rewrite)
- Modify: `src/alphaloop/runtime/api.py`, `src/alphaloop/runtime/daemon.py`, `src/alphaloop/runtime/client.py`, `src/alphaloop/cli/jobs.py`
- Modify: `src/alphaloop/webui/static/index.html`, `app.js`, `styles.css`
- Modify: `docs/webui.md`, `mkdocs.yml`
- Test: `tests/runtime/test_api.py`, `tests/runtime/test_http.py`, `tests/runtime/test_static_console.py`, `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Failing tests**

HTTP: POST `/v1/jobs/{id}/replay` writes `report.md` and returns `run_id`.

Static: `#replay-job` in HTML after `#resume-job` and before `#report`; `/replay` in JS.

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_http.py::test_http_replay_rewrites_report -v
```

- [ ] **Step 3: Implement**

Shared rewrite, JobAPI.replay_run, daemon route, console button + click.

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(webui): replay report.md from the morning console"
```
