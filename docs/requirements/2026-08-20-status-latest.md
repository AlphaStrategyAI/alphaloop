---
title: "CLI status without a run id leads with the latest job"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.3 / §10.2"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-cli-status-verdict.md
  - docs/requirements/2026-08-20-morning-lead.md
  - docs/requirements/2026-08-20-empty-morning.md
---

# CLI status without a run id leads with the latest job

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Optional `RUN_ID` on `alphaloop status`. Not a new hard
gate. Not inventing `FOUND`. Not unfreezing `webui/`. Not soak
execution. Not \(N_{\mathrm{eff}}\). Not changing `cancel` /
`resume`.

## 1. Why this cycle exists

PRD §4.3: the morning surface leads with **one** conclusion. The
packaged console already newest-first auto-opens `jobs[0]`. PRD §10.2
makes the CLI a first-class morning surface for the AI-native /
terminal user.

`alphaloop status` still requires a `j_*` id. A researcher who
submitted before bed and types `status` in the morning must recall
the id. Nielsen: recognition rather than recall. That is not a
five-minute terminal review.

## 2. Best-practice basis

1. **Same latest-job rule as the Web home.** `JobStore.list_jobs` is
   already `ORDER BY created_at DESC, run_id DESC`. CLI uses
   `jobs[0]`.
2. **Empty state names the next action**, not a fake conclusion. Do
   not mint a job or `FOUND`.
3. **Do not break the explicit-id path.** `alphaloop status RUN_ID`
   still prints the verdict whose first line is the outcome token.
   `--json` with a run id is still that job's `morning_view`.

## 3. In-scope requirements

### R1. Optional `RUN_ID`

`alphaloop status [RUN_ID] [--json]` accepts a missing run id.

When `RUN_ID` is present, behavior is unchanged from
`docs/requirements/2026-08-20-cli-status-verdict.md`.

### R2. Latest job

When `RUN_ID` is omitted and `GET /v1/jobs` returns a non-empty
`jobs` list, default stdout is:

1. `run_id: {jobs[0].run_id}`
2. then `format_status_verdict(jobs[0])` (same cluster as today)

`--json` without a run id prints `json.dumps(jobs[0], sort_keys=True)`
— the same object as `alphaloop status {that id} --json`.

### R3. Empty cue

When `RUN_ID` is omitted and `jobs` is empty, default stdout is
exactly this locked paragraph plus a newline:

`No overnight job yet. Submit a frozen spec with alphaloop submit --spec PATH. This status does not claim alpha or future profitability.`

`--json` empty prints `{"jobs": []}` (sorted keys). Exit code is 0.
The text MUST NOT contain `target found`. It MUST NOT claim `FOUND`.

### R4. Docs and Skill

CLI help, `docs/cli.md`, README / docs index, and the overnight-lab
Skill MUST say `alphaloop status` reviews the latest job, and that
agents may parse `alphaloop status --json` or
`alphaloop status RUN_ID --json`.

`HOST_CONSTRAINT` / Help / example YAML unchanged.

## 4. Out of scope

- Soak execution. \(N_{\mathrm{eff}}\). MCP / cloud workers.
- Unfreezing `webui/`. A dedicated `alphaloop jobs` list command.
- Human-formatting `cancel` / `resume`.

## 5. Acceptance

- Parser: `status` with no positional is valid; `--json` is not a
  run id.
- Unit: empty daemon → locked cue / `{"jobs": []}`; two jobs →
  newest `run_id` leads.
- Explicit `status RUN_ID` first line remains the outcome token.
- E2E: after a submit, `alphaloop status` first line is
  `run_id: {that id}` and the next line is the page `#outcome`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.

## 6. Loop exit

Remaining first-release items: soak **execution** on an awake host
(not CI); correlation-adjusted \(N_{\mathrm{eff}}\) must not shrink
DSR `N`. Later: MCP / cloud workers.
