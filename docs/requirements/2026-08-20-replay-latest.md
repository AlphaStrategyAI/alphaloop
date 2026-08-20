---
title: "CLI replay without a run id uses the latest job"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-replay-verdict.md / cancel-latest.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-replay-verdict.md
  - docs/requirements/2026-08-20-cancel-latest.md
  - docs/requirements/2026-08-20-export-latest.md
  - docs/requirements/2026-08-20-status-latest.md
---

# CLI replay without a run id uses the latest job

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Optional `RUN_ID` on `alphaloop replay`. Not a new hard gate.
Not inventing `FOUND`. Not unfreezing `webui/`. Not soak. Not
\(N_{\mathrm{eff}}\). Not changing the five-minute verdict cluster.
Not requiring the daemon. Not changing `cancel` / `resume` / `status` /
`export`.

## 1. Why this cycle exists

PRD §3.4 / §10.2: replay rewrites `report.md` from sealed artifacts and
prints the five-minute cluster. `status`, `export`, `cancel`, and
`resume` already omit the id for the latest job. `replay` still requires
a `j_*` token.

A morning reader who just ran `alphaloop status` must recall the id to
regenerate the paper view. Nielsen: recognition rather than recall.

Replay stays **offline**. Resolve latest from `JobStore.list_jobs()[0]`
like export, not `GET /v1/jobs`.

## 2. Best-practice basis

1. **Same latest-job rule.** `ORDER BY created_at DESC, run_id DESC`.
2. **Do not invent FOUND.** Empty store: stderr + exit 2, no verdict
   cluster. Do not use the status empty cue (that path is not a replay).
3. **Keep the explicit id.** `alphaloop replay RUN_ID` unchanged,
   including first-line outcome token (no `run_id:` prefix).
4. **When omitted, name the job.** Default stdout starts with
   `run_id: {jobs[0].run_id}` then `format_status_verdict`.
5. **Stay offline.** Missing daemon is not an error. Missing run
   directory after resolve stays the existing exit 2.

## 3. In-scope requirements

### R1. Optional `RUN_ID`

`alphaloop replay [RUN_ID]` accepts a missing run id. `--json` unchanged
except as in R2.

### R2. Latest job

When omitted and `JobStore.list_jobs()` is non-empty, replay
`jobs[0].run_id`. Human omit path:

1. `run_id: {id}`
2. then the existing verdict cluster

`--json` omit path is `json.dumps` of the existing artifact view plus
`run_id` of that job (`sort_keys=True`). No extra prefix line.

Explicit `replay RUN_ID` JSON MAY omit `run_id` (current payload).

### R3. Empty store

When omitted and there are no jobs, stderr is exactly:

`error: no overnight job yet`

plus a newline. Exit 2. MUST NOT print `FOUND` on stdout. MUST NOT
contain `target found`. MUST NOT require the daemon.

### R4. Docs

`docs/cli.md`, README workflow block, Skill, and `docs/index.md` MAY
say omit `RUN_ID` for the latest job. Index MAY also show optional
`cancel` / `resume` to match shipped CLI.

## 4. Out of scope

- Re-running gates. Minting `FOUND`. Soak. \(N_{\mathrm{eff}}\).
  FakeWorker in morning e2e. Unfreezing `webui/`. Changing verdict copy.
  Searching older jobs for sealed `FOUND`.

## 5. Acceptance

- Unit: omit id replays latest; empty store exit 2 locked stderr;
  explicit id stdout still starts with the outcome token; omit path
  does not need a daemon.
- E2E: existing console paths unchanged.
- Locks: no invented `FOUND`. Replay still offline.
