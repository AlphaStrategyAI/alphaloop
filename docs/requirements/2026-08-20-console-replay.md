---
title: "Morning Replay report rewrites report.md without inventing FOUND"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-replay-verdict.md / replay-latest.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-replay-verdict.md
  - docs/requirements/2026-08-20-replay-latest.md
  - docs/requirements/2026-08-20-lifecycle-actions.md
---

# Morning Replay report rewrites report.md without inventing FOUND

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged `#replay-job` and `POST /v1/jobs/{run_id}/replay`.
Not a new hard gate. Not inventing `FOUND`. Not re-running gates.
Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\).
Not changing CLI replay stdout.

## 1. Why this cycle exists

PRD §3.4 / §10.1: the packaged console is the primary five-minute
surface. CLI `alphaloop replay` already rewrites `report.md` from
sealed artifacts and prints the verdict cluster. The morning page
shows `#report` but has no Replay control.

A morning reader who wants the paper view regenerated must leave the
console for the terminal. Nielsen: recognition rather than recall.
Same offline derivation as CLI replay (sealed `gates.json`, no gate
re-run).

## 2. Best-practice basis

1. **Same writer as CLI.** Shared `rewrite_sealed_report`. MUST NOT
   mint `FOUND`. MUST NOT re-run diagnostics.
2. **Controls next to the report.** `#replay-job` sits in the existing
   `.actions` node with Cancel/Resume, above `#report`.
3. **Always available on a selected job.** Do not hide Replay by job
   status. `#detail` already hides the cluster when there is no job.
4. **Secondary chrome, not FOUND green.** Same family as Load example
   (`--ink` / `--fg` / `--line`). MUST NOT use `--accent`.
5. **After click, refresh the selected job** so `#report` shows the
   rewritten markdown.

## 3. In-scope requirements

### R1. API

`POST /v1/jobs/{run_id}/replay` rewrites `report.md` and returns
`morning_view` for that job. Unknown `run_id` is 404. Missing run
directory is 404. Does not change `research_outcome` in sqlite.

### R2. Console

Packaged `#detail` `.actions` MUST include `#replay-job` labeled
`Replay report`. DOM order:

`#resume-job` < `#replay-job` < `#report`

Click POSTs `/v1/jobs/{id}/replay` then reloads the selected job.
Hide/show of Cancel/Resume unchanged. Replay is not `hidden`.

### R3. Chrome

`#replay-job` MUST use `--ink` background, `--fg` color, `--line`
border. That rule MUST NOT contain `var(--accent)`.

### R4. Docs

`docs/webui.md` / `docs/cli.md` MAY mention console Replay. Skill MAY
say the page can rewrite `report.md`. Help / EXAMPLE_SPEC /
`HOST_CONSTRAINT` unchanged.

## 4. Out of scope

- Changing CLI replay stdout. Re-running gates. Soak.
  \(N_{\mathrm{eff}}\). FakeWorker in morning e2e. Unfreezing
  `webui/`. Auto-export.

## 5. Acceptance

- Unit/HTTP: POST replay writes `report.md`, returns morning_view,
  unknown id 404; sqlite outcome unchanged.
- Static: `#replay-job`, `/replay` in JS, CSS without `--accent`.
- E2E: click Replay report; `#report` contains the locked no-alpha
  sentence; page `#outcome` unchanged.
- Locks: no invented `FOUND`.
