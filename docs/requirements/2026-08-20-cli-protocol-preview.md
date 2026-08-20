---
title: "CLI previews the compiled protocol before freeze"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.1 / §10.2"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-protocol-preview.md
  - docs/requirements/2026-08-20-status-latest.md
---

# CLI previews the compiled protocol before freeze

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `alphaloop preview --spec PATH` over the existing
`POST /v1/jobs/preview` contract. Not a new hard gate. Not inventing
`FOUND`. Not unfreezing `webui/`. Not soak execution. Not
\(N_{\mathrm{eff}}\). Not auto-submit.

## 1. Why this cycle exists

PRD §4.1 step 4: the user **reviews and freezes** the research
protocol before the worker starts. The packaged console already has
Preview protocol → Freeze. Protocol-preview requirements left CLI
submit as a single freeze: sending the file *was* the review.

CLI is now a first-class before-bed / morning surface (`status`
verdict, latest job). A terminal user still cannot see
`planned_n_trials` or the method grid before `submit` creates a job.
Bailey / López de Prado: disclose **N** before treating later
Sharpes as evidence. Nielsen: error prevention before an overnight
job on the user's machine.

## 2. Best-practice basis

1. **Reuse the preview API.** `JobAPI.preview_run` already runs
   preflight + `method_parameter_grid` and does not call
   `store.create`. CLI must not invent a second preview.
2. **Same summary fields as the packaged `#protocol-preview`.**
   `spec_id`, statement, signal_mechanism, hard_gates,
   `planned_n_trials`, then one grid row per parameter dict.
3. **Do not create a job.** No `run_id`. Preflight failure is not
   `FOUND`. Missing dataset still says `dataset snapshot is required`.
4. **Human default, `--json` for agents.** Same pattern as `status`.

## 3. In-scope requirements

### R1. `JobClient.preview_run`

`JobClient.preview_run(spec) -> dict` POSTs the spec to
`/v1/jobs/preview` and returns the preview object. It MUST NOT POST
`/v1/jobs`.

### R2. `alphaloop preview --spec PATH`

Register `preview` next to `submit`. Required `--spec`. Optional
`--data-dir`, `--json`.

Default stdout, when parse succeeds:

```
spec_id: {spec_id}
statement: {statement}
signal_mechanism: {signal_mechanism}
hard_gates: {comma-separated names}
planned_n_trials: {n}
grid:
{one line per method_parameter_grid row, sorted k=v, or {}}
```

Then `HOST_CONSTRAINT` (verbatim). Then the locked sentence:

`This preview does not claim alpha or future profitability.`

When `ok` is true, a final line:

`Freeze with alphaloop submit --spec PATH`

When `ok` is false, print each preflight error on its own line
**before** the cluster (or instead of the freeze line). Do not print
the freeze cue. Exit 2. Still no job.

`--json` prints `json.dumps(preview, sort_keys=True)`. Exit 0 iff
`ok` is true. `--json` MUST NOT include a `run_id` key.

Default stdout MUST NOT contain `target found`. MUST NOT contain
`run_id:`.

Daemon down → same `alphaloop start` hint as submit (exit 2).

### R3. Empty status cue

Replace `EMPTY_STATUS_CUE` with, verbatim plus newline:

`No overnight job yet. Preview with alphaloop preview --spec PATH, then freeze with alphaloop submit --spec PATH. This status does not claim alpha or future profitability.`

### R4. Docs and Skill

`docs/cli.md`, README / docs index, parser help, and the overnight-lab
Skill MUST name `alphaloop preview --spec PATH` as the review step
that does not create a job. Help / `HOST_CONSTRAINT` / example YAML
unchanged except the empty-status cue above.

## 4. Out of scope

- Requiring preview before submit (CLI freeze may still be one
  command, as today). The Skill teaches preview-then-submit.
- Soak execution. \(N_{\mathrm{eff}}\). MCP / cloud. Unfreezing
  `webui/`.

## 5. Acceptance

- Unit: parser has `preview`; preview with `_cached_spec` prints
  `planned_n_trials`, `HOST_CONSTRAINT`, freeze cue, no `run_id`,
  `list_jobs` still empty.
- Unit: missing dataset → exit 2, `dataset snapshot is required`, no
  job.
- Unit: empty `alphaloop status` uses the new cue.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.

## 6. Loop exit

Remaining first-release items: soak **execution** on an awake host
(not CI); correlation-adjusted \(N_{\mathrm{eff}}\) must not shrink
DSR `N`. Later: MCP / cloud workers.
