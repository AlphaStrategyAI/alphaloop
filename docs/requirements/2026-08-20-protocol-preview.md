---
title: "Protocol preview before freeze"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-honest-docs-morning-help.md
---

# Protocol preview before freeze

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Web console and Job API preview of the compiled overnight
protocol *before* a job is created. Not CPCV. Not a trading UI. Not an
in-run protocol editor.

## 1. Why this cycle exists

PRD §4.1 Before bed:

1. Open the local Web console or CLI.
2. State a hypothesis and choose a market profile.
3. Preflight data, gates, budgets, disk.
4. **The user reviews and freezes the research protocol.**
5. Submission returns a `run_id` immediately.

Today YAML POST `/v1/jobs` creates the job immediately. The user cannot
see the method-parameter grid, planned trial count, `spec_id`, or
preflight result before the worker starts. Bailey and López de Prado
require disclosing **what will be tried** (`N` trials) before treating
a later Sharpe as evidence. Nielsen's **error prevention** heuristic
asks for a review step before an irreversible action (an overnight
job on the user's machine).

CLI `alphaloop submit` remains a single freeze: sending the file is
the review. This cycle is the packaged morning page plus a preview
API that does not create a job.

## 2. In-scope requirements

### R1. `JobAPI.preview_run(spec) -> dict`

Must run `preflight(spec, data_dir)` and `method_parameter_grid` for
`spec.hypothesis.signal_mechanism`. Must **not** call `store.create`.
Must **not** start a worker.

Returned keys:

- `ok`: `preflight.ok`
- `errors`: list of preflight error strings (empty when ok)
- `host_constraint`: `HOST_CONSTRAINT`
- `spec_id`, `seed`, `statement`, `signal_mechanism`
- `hard_gates`: list of required gate names
- `method_parameter_grid`: list of parameter dicts (JSON-serializable)
- `planned_n_trials`: `len(method_parameter_grid)`
- `time_budget_s`, `cost_budget_usd`

Unknown DSL kinds still get the protocol grid `[{}]` (one default
trial), matching `method_parameter_grid` today. Preflight still
rejects unknown kinds; then `ok` is false.

### R2. `POST /v1/jobs/preview`

Same body parsing as `POST /v1/jobs` (JSON or YAML). 200 with the
preview dict when the payload parses. 400 `{"error": ...}` on parse
failure. Never 201. Never a `run_id`.

`GET /v1/jobs/preview` must not create a job named `preview`.

### R3. Packaged page: preview, then freeze

- `#preview-protocol` button, always enabled.
- `#protocol-preview` element shows the compiled protocol after a
  successful parse (grid, `planned_n_trials`, `spec_id`, statement,
  gates, budgets, host constraint). On preflight failure it shows
  `errors` and does not enable freeze.
- `#submit-job` (Freeze and submit) is **disabled** until the latest
  successful preview (`ok: true`) was for the **current** textarea
  contents. Editing the textarea disables submit again.
- Freeze POSTs `/v1/jobs` as today. Preview POSTs `/v1/jobs/preview`.
- No gate override. Do not invent `FOUND`.

Button label for `#submit-job` MAY stay `Submit` or become
`Freeze and submit`. Tests key off the id.

### R4. Docs

One short paragraph in `docs/webui.md` first-release lead: preview the
protocol, then freeze. Do not describe preview as finding alpha.

## 3. Out of scope

- Changing CLI `submit` into a two-step prompt.
- Editing the grid in the UI.
- Protocol preview-and-freeze on MCP.
- CPCV / new gates / new DSL kinds.
- FakeWorker in morning e2e.
- Changing `HOST_CONSTRAINT`.

## 4. Acceptance

- Unit: `preview_run` does not create jobs; grid and `planned_n_trials`
  match `method_parameter_grid`; failed preflight sets `ok` false.
- Integration: HTTP preview 200, job list still empty; create still 201.
- E2E: preview alone creates no job row; freeze after preview submits;
  editing YAML after preview keeps submit disabled until preview again.
