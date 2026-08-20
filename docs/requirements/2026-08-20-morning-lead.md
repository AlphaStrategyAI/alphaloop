---
title: "Morning home leads with the latest job"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.3"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-search-progress.md
  - docs/requirements/2026-08-20-funnel-bars.md
---

# Morning home leads with the latest job

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning console job list order, auto-open of the
latest job, live detail refresh, and a mini elimination funnel on
each job card. Not a new `HardGateName`. Not unfreezing `webui/`.
Not soak. Not inventing `FOUND`.

## 1. Why this cycle exists

PRD §4.3: the morning **home page leads with one conclusion**, then
evidence, funnel, revisions, and queued hypotheses. Today `#detail`
stays `hidden` until the user clicks a job. The list is
`ORDER BY created_at` ascending, so last night sits at the bottom.
Job cards show search progress but not how the grid died — that
named remaining item from
`docs/requirements/2026-08-20-search-progress.md` §6.

A five-minute reader who opens the console after an overnight run
should see the latest conclusion without hunting. Nielsen heuristic 1:
system status should be visible. Tufte: encode funnel counts as
length on the card, not only after a click.

A new economic hypothesis is still never executed silently.

## 2. Best-practice basis

1. **Recognition over recall:** do not require remembering which
   `j_*` id was last night.
2. **Newest first** is the standard overnight-inbox order.
3. **Live refresh:** the existing 2s job-list poll should also
   refresh the open detail so search progress and funnel move while
   the host is awake. Do not imply alpha.

## 3. In-scope requirements

### R1. Newest-first list

`JobStore.list_jobs` MUST return `ORDER BY created_at DESC, run_id DESC`.
The packaged list renders that order. The first card is the latest job.

### R2. Auto-open and live detail

When the job list is non-empty and no job is selected, the console
MUST open the first (latest) job: `#detail` unhidden, `#outcome`
filled. After submit, select the created `run_id`. If the selected
id leaves the list, fall back to the latest remaining job. If the
list is empty, `#detail` stays hidden.

`loadJobs` MUST refresh the selected detail (same `showJob` path)
so a running job's search bar and funnel update on the existing
poll. Clicking a card still selects that job. `aria-current="true"`
on the selected card.

### R3. Mini-funnel on the card

Each job button MUST include `.job-funnel`. When the job's
`funnel` has any of `n_evaluated`, `n_passed`, `n_failed`,
`n_incomplete` greater than zero, render the same three-segment
`.funnel-stack` encoding as `#funnel-bars` (passed / failed /
incomplete, `data-pct`). Zero-count jobs render an empty
`.job-funnel` (no stack). Do not invent `FOUND`.

### R4. Locks

`HOST_CONSTRAINT` unchanged. Help sentences unchanged. Example YAML
unchanged. No `FakeWorker` in morning e2e. Packaged page only.

## 4. Out of scope

- Textbook `S=16` CPCV. Soak / 95% overnight as CI.
- Correlation-adjusted \(N_{\mathrm{eff}}\). MCP / cloud workers.
- Unfreezing `webui/`. Changing protocol search.

## 5. Acceptance

- Unit: two created jobs list newest first.
- Packaged assets: `aria-current`, `job-funnel`, `fillFunnelStack`
  or equivalent stack helper; CSS for `.job-funnel .funnel-stack`.
- E2E: empty home keeps `#detail` hidden; after submit, `#detail`
  becomes visible without requiring a click; a terminal job card
  contains `.job-funnel .funnel-stack`. Do not invent `FOUND`.

## 6. Loop exit

Remaining validation: textbook `S=16` CPCV, soak / 95% overnight
(not CI), correlation-adjusted \(N_{\mathrm{eff}}\). Later: MCP /
cloud workers.
