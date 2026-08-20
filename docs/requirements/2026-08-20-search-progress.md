---
title: "Overnight search progress on the frozen grid"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.2"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-funnel-bars.md
  - docs/requirements/2026-08-20-protocol-preview.md
---

# Overnight search progress on the frozen grid

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Expose `planned_n_trials` on `morning_view` and render a
search-progress bar on the packaged job list and job detail. Not a
new `HardGateName`. Not unfreezing `webui/`. Not soak. Not inventing
`FOUND`.

## 1. Why this cycle exists

Protocol preview already shows `planned_n_trials` (length of the
frozen `method_parameter_grid`). After submit, the job card only
shows `n_trials: N`. Nielsen's **visibility of system status** says
a running overnight job must show how far the predeclared search
has walked, not only how many ledger ids exist. A user who left a
three-point MACD grid running cannot tell 0/3 from 2/3 without
opening YAML.

`docs/requirements/2026-08-20-funnel-bars.md` §6 deferred "live
in-run progress." This cycle takes that named remaining check.
The bar is **search progress**, not progress toward alpha.

## 2. Best-practice basis

1. **NN/g heuristic 1:** running vs sealed stays distinct; the
   denominator is the frozen grid, not a moving target.
2. **Tufte:** length encodes `n_trials / planned_n_trials`. Do not
   use a spinner that hides the count.
3. **Honesty:** stopping early on `FOUND` leaves the bar short of
   100%. That is correct. Do not fill the bar on `FOUND` unless
   `n_trials` actually reached the plan.

## 3. In-scope requirements

### R1. `planned_n_trials` on morning_view

`morning_view` MUST include `planned_n_trials: int` equal to
`len(method_parameter_grid(signal_mechanism))`, the same rule as
`JobAPI.preview_run`. Unknown kinds stay length 1 (`({})`).

### R2. Job card and detail bar

Job list buttons MUST show `search: {n_trials} / {planned_n_trials}`
(keep the existing `n_trials` substring) and a `.search-progress`
track whose `.search-progress-fill` has `data-pct` = integer
percent of `max(planned_n_trials, 1)`, capped at 100.

Job detail MUST include `#search-progress` with the same fill
encoding, and `#spec-meta` MUST include `planned_n_trials`.

### R3. Locks

`HOST_CONSTRAINT` unchanged. Help sentences unchanged. Example YAML
unchanged. No `FakeWorker` in morning e2e. No invented `FOUND`.
Packaged page only.

## 4. Out of scope

- Job-list mini-funnel (passed/failed stack). Textbook `S=16`. Soak.
- Correlation-adjusted \(N_{\mathrm{eff}}\). MCP / cloud workers.

## 5. Acceptance

- Unit: `morning_view` for `momentum_12_1` has `planned_n_trials == 3`.
- Packaged assets: JS writes `.search-progress-fill` and
  `search: `; CSS defines `.search-progress`.
- E2E: job card contains `/` with planned count; detail
  `#search-progress .search-progress-fill` has `data-pct`.
  Do not invent `FOUND`.

## 6. Loop exit

Remaining product: job-list mini-funnel. Remaining validation:
textbook `S=16` CPCV, soak / 95% overnight (not CI),
correlation-adjusted \(N_{\mathrm{eff}}\). Later: MCP / cloud workers.
