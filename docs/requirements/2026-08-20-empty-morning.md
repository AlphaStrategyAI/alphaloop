---
title: "Empty morning list cues one-minute submit without inventing a job"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.1 / §4.3"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-19-five-minute-morning-review.md
---

# Empty morning list cues one-minute submit without inventing a job

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged console empty job list, plus honest ROADMAP remaining
work. Not a new job. Not inventing `FOUND`. Not unfreezing `webui/`.
Not soak execution. Not \(N_{\mathrm{eff}}\).

## 1. Why this cycle exists

The product promise starts with **submit in one minute**. On first
open, `#detail` is hidden and `#job-list` is empty. Nielsen:
recognition rather than recall. A first-run researcher has to invent
the Load example → Preview → Freeze path from the left column alone.

`ROADMAP.md` remaining items 2–3 still describe protocol preview and
qualifying/funnel as unfinished. Those shipped. Docs that sell a
different product destroy trust (five-minute review R6).

## 2. Best-practice basis

1. **Empty state names the next action**, not a fake conclusion.
2. **Do not mint a job or `FOUND`.** The cue is copy only.
3. **Honest remaining work.** Preview, qualifying list, funnel, and
   verdict handoff are current first-release surface. Soak execution
   on an awake host, \(N_{\mathrm{eff}}\) (must not shrink DSR `N`),
   and later MCP/cloud remain.

## 3. In-scope requirements

### R1. `#empty-morning`

Packaged `#jobs` MUST include `#empty-morning` after `#job-list`.
Locked text, verbatim:

`No overnight job yet. Load example, then Preview protocol, then Freeze and submit. This console does not claim alpha or future profitability.`

`loadJobs`: if the job array is empty, `#empty-morning` is visible
(`hidden` false). If any job exists, `#empty-morning` is `hidden`.
`#detail` stays hidden when there is no selected job.

The node MUST NOT be a `#job-list button`. HOST_CONSTRAINT stays in
Help / `#host-constraint` only.

### R2. ROADMAP remaining work

Replace remaining items 2–3 so they do not list shipped preview /
qualifying / funnel as unfinished. Keep soak **execution** (not the
print command), \(N_{\mathrm{eff}}\) not shrinking DSR `N`, and later
MCP / cloud workers.

### R3. Locks

Help sentences unchanged. Example YAML unchanged. No FakeWorker in
morning e2e. No gate override.

## 4. Out of scope

- Auto-loading the example. Auto-submit. Running overnight soak.
- \(N_{\mathrm{eff}}\). Unfreezing `webui/`.

## 5. Acceptance

- Static: `#empty-morning` after `#job-list`; `loadJobs` toggles
  `hidden`.
- E2E: first open shows the locked sentence; after a submit the node
  is hidden; `#job-list button` count rules unchanged.
- ROADMAP remaining list no longer claims preview/funnel unshipped.
- Unit + e2e pytest as usual.

## 6. Loop exit

Remaining: human overnight soak; \(N_{\mathrm{eff}}\) must not shrink
DSR `N`; later MCP / cloud workers.
