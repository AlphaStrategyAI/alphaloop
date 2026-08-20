---
title: "Morning revisions list only in-run method repairs"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.3 / §6.1"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-frozen-grid-honest-kinds.md
  - docs/requirements/2026-08-20-morning-lead.md
---

# Morning revisions list only in-run method repairs

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `morning_view["revisions"]` and the packaged `#revisions`
list. Not a new hard gate. Not inventing `FOUND`. Not changing the
trial ledger. Not shrinking DSR `N` / unique `n_trials`. Not unfreezing
`webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not restyling chrome.

## 1. Why this cycle exists

PRD §4.3: after the conclusion, the morning page presents qualifying
candidates, the funnel, **methodological revisions made during the
run**, then queued future hypotheses. PRD §6.1: the first frozen
hypothesis is immutable; the loop may repair **method** (including
insufficient but relevant parameter coverage) and record each repair
in the ledger.

`run_protocol` already writes `revision: "none"` for the first frozen
grid point and `revision: "method"` for later frozen points. Economic
revisions stay in `queued_hypotheses`. `morning_view["revisions"]`
still dumps **every** trial-ledger row. A five-minute reader sees the
starting point labeled as a revision. Nielsen: match the system to
the real world. Tufte: do not display the whole ledger under a
heading that means a subset.

Unique-ledger `n_trials` (DSR `N`) MUST still count every trial id.

## 2. Best-practice basis

1. **A revision is a repair, not the freeze.** Rows with
   `revision == "none"` (or missing / empty) MUST NOT appear in
   `revisions`.
2. **Do not shrink N.** `_n_trials` / DSR still use the full ledger.
3. **Empty is honest.** When no method rows exist, `revisions` is `[]`
   and the packaged list keeps fillList `none`. MUST NOT print
   `FOUND`.
4. **Queued stays economic.** Do not move `queued_hypotheses` into
   `#revisions`.

## 3. In-scope requirements

### R1. Filter

`morning_view["revisions"]` MUST be the trial-ledger dict rows whose
`revision` field equals `"method"`, in ledger order. Other rows remain
on disk.

### R2. `n_trials` unchanged

`morning_view["n_trials"]` MUST remain the unique `trial_id` count
over the **full** ledger, including `revision: none`.

### R3. Console

`#revisions` still renders `job.revisions` via `fillList`. Empty →
`none`. Line format unchanged (`trial_id · revision · params`).

### R4. Docs

`docs/webui.md` MUST say the methodological revisions list is in-run
method repairs, not the first frozen grid point.

## 4. Out of scope

- Changing ledger write format. New revision kinds. Soak.
  \(N_{\mathrm{eff}}\). Unfreezing `webui/`. Evidence-line glosses.
  Market-profile glosses.

## 5. Acceptance

- Unit: ledger with `none` then `method` → `revisions` is only the
  method row; `n_trials` counts both ids.
- Unit: ledger with only `none` → `revisions == []`; queued hypotheses
  still load.
- Existing unique-`n_trials` test stays green.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
