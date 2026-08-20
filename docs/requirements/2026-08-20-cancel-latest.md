---
title: "CLI cancel and resume without a run id use the latest job"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-cancel-resume-verdict.md / status-latest.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-cancel-resume-verdict.md
  - docs/requirements/2026-08-20-status-latest.md
  - docs/requirements/2026-08-20-export-latest.md
---

# CLI cancel and resume without a run id use the latest job

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Optional `RUN_ID` on `alphaloop cancel` and
`alphaloop resume`. Not a new hard gate. Not inventing `FOUND`.
Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\).
Not changing the five-minute verdict cluster. Not changing `replay`.

## 1. Why this cycle exists

PRD §5.3 / §10.2: stop and resume are first-class overnight controls.
The console Cancel/Resume act on the selected job, which defaults to
the latest. `status` and `export` already omit the id for latest.
`cancel` and `resume` still require a `j_*` id.

A researcher who sees a running pulse or a failed recovery must recall
the id to stop or resume from the terminal. Nielsen: recognition
rather than recall.

## 2. Best-practice basis

1. **Same latest-job rule as status/export.** `jobs[0]` newest-first.
2. **Do not invent FOUND.** Empty store: stderr + exit 2, no verdict
   cluster. Do not use the status empty cue (that path is not a
   cancel).
3. **Keep the explicit id.** `alphaloop cancel RUN_ID` unchanged,
   including first-line outcome token (no `run_id:` prefix).
4. **When omitted, name the job.** Default stdout starts with
   `run_id: {jobs[0].run_id}` then `format_status_verdict`, matching
   `status` without an id.

## 3. In-scope requirements

### R1. Optional `RUN_ID`

`alphaloop cancel [RUN_ID]` and `alphaloop resume [RUN_ID]` accept a
missing run id. `--json` unchanged.

### R2. Latest job

When omitted and `GET /v1/jobs` is non-empty, act on `jobs[0]`.
Human omit path:

1. `run_id: {id}`
2. then the existing verdict cluster

`--json` omit path is `json.dumps(morning_view, sort_keys=True)` for
that job (includes `run_id`; no extra prefix line).

### R3. Empty store

When omitted and `jobs` is empty, stderr is exactly:

`error: no overnight job yet`

plus a newline. Exit 2. MUST NOT print `FOUND` on stdout. MUST NOT
contain `target found`. Daemon-unavailable stays the existing start
hint.

### R4. Docs

`docs/cli.md`, README workflow block, and Skill MAY say omit `RUN_ID`
for the latest job. README export line MAY drop required `--run-id`
to match shipped export-latest.

## 4. Out of scope

- Changing hide/show of console Cancel/Resume. Soak. \(N_{\mathrm{eff}}\).
  FakeWorker in morning e2e except existing CLI tests. Unfreezing
  `webui/`. Optional `replay` id.

## 5. Acceptance

- Unit: omit id cancels/resumes latest; empty store exit 2 locked
  stderr; explicit id stdout still starts with the outcome token.
- E2E: existing console cancel still works (unchanged).
- Locks: no invented `FOUND`.
