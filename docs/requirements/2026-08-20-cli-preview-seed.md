---
title: "CLI protocol preview discloses N, seed, and budgets"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-cli-protocol-preview.md / 2026-08-20-preview-card.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-cli-protocol-preview.md
  - docs/requirements/2026-08-20-preview-card.md
---

# CLI protocol preview discloses N, seed, and budgets

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Human stdout of `alphaloop preview --spec PATH` via
`format_protocol_preview`. Not a new hard gate. Not inventing `FOUND`.
Not changing `preview_run` keys. Not requiring preview before submit.
Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not
restyling the packaged preview card.

## 1. Why this cycle exists

Protocol-preview R3 required disclosing grid, `planned_n_trials`,
`spec_id`, statement, gates, **budgets**, and host constraint before
Freeze. The packaged `#protocol-preview` card now leads with
`planned_n_trials` and prints `seed:`, `time_budget_s:`, and
`cost_budget_usd:`. `preview_run` already returns those keys.

CLI `format_protocol_preview` still omits seed and budgets, and prints
`spec_id` before N. A terminal researcher reviewing the same compiled
protocol does not see the frozen seed or overnight budgets. Bailey /
López de Prado: disclose **N** and the seed before treating a later
Sharpe as evidence. Nielsen: recognition — the CLI and the morning
card must name the same frozen facts.

`--json` already dumps the full payload. This cycle is human stdout.

## 2. Best-practice basis

1. **Lead with N.** The first line of the protocol cluster (after any
   preflight errors) MUST be `planned_n_trials: {n}`.
2. **Disclose seed and budgets.** Human stdout MUST contain `seed:`,
   `time_budget_s:`, and `cost_budget_usd:` from the preview payload,
   before `grid:`.
3. **Do not create a job.** No `run_id`. Do not print `FOUND`. Keep
   `HOST_CONSTRAINT` and the locked no-alpha sentence.
4. **Do not invent keys.** Read `seed`, `time_budget_s`, and
   `cost_budget_usd` from `preview_run`. Do not change the Job API.

## 3. In-scope requirements

### R1. Lead N

When formatting a preview body, the protocol cluster MUST start with:

```
planned_n_trials: {planned_n_trials}
```

Preflight errors, when `ok` is false, remain **above** that cluster.

### R2. Seed and budgets

The cluster MUST then include, in this order:

```
spec_id: {spec_id}
statement: {statement}
signal_mechanism: {signal_mechanism}
hard_gates: {comma-separated names}
seed: {seed}
time_budget_s: {time_budget_s}
cost_budget_usd: {cost_budget_usd}
grid:
```

Then one line per `method_parameter_grid` row (existing `k=v` sort).
Then `HOST_CONSTRAINT` (verbatim). Then:

`This preview does not claim alpha or future profitability.`

When `ok` is true, keep the freeze cue:

`Freeze with alphaloop submit --spec PATH`

### R3. Docs

`docs/cli.md` MUST name seed and budgets among the fields human
preview prints. Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC / empty-status
cue stay locked.

## 4. Out of scope

- Requiring preview before CLI submit.
- Changing `--json` (already the full payload).
- Changing `preview_run`. Soak. \(N_{\mathrm{eff}}\). Unfreezing
  `webui/`. Packaged card chrome.

## 5. Acceptance

- Unit: `format_protocol_preview` first protocol line is
  `planned_n_trials:`; text contains `seed:`, `time_budget_s:`,
  `cost_budget_usd:`; no `run_id:`; no `FOUND`.
- Existing `test_preview_shows_protocol_without_creating_a_job` stays
  green (still no job).
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
