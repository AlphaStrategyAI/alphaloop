---
title: "Morning elimination funnel as proportional bars"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.3"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-morning-funnel.md
  - docs/requirements/2026-08-19-five-minute-morning-review.md
---

# Morning elimination funnel as proportional bars

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged static morning console visualization of the
existing `morning_view.funnel` payload. Not a new `HardGateName`.
Not unfreezing the Vite SPA under `webui/`. Not soak. Not inventing
`FOUND`.

## 1. Why this cycle exists

PRD §4.3 requires the morning page to show **the candidate
elimination funnel and dominant failure reasons** after the
conclusion. The funnel cycle already aggregates search-wide counts
(`n_evaluated`, `n_passed`, `n_failed`, `n_incomplete`,
`failure_counts`). The packaged page still renders those as muted
text (`evaluated: 3 · passed: 0 · failed: 3`) and a list
(`dsr × 3`). A five-minute reader must parse numbers to see that
the grid died. Nielsen's **visibility of system status** and
Tufte's **smallest effective difference** both say: encode the
magnitudes as length.

`docs/requirements/2026-08-20-majority-folds.md` §4 deferred
"funnel bar charts or other visual polish." This cycle takes that
named remaining check. The product goal also requires a visually
distinct, intuitively interactive console — not a second Quant Lab
SPA.

## 2. Best-practice basis

1. **Tufte:** length is the least error-prone encoding for counts.
   Do not use pie charts. Do not decorate empty zero-trial states.
2. **NN/g heuristic 1:** system status should be visible, not only
   readable. Passed vs failed vs incomplete must be distinguishable
   by the existing outcome colors (accent / warn / inconclusive).
3. **CONSORT honesty:** the bar total is `n_evaluated`. Do not draw
   a 100% "passed" bar when evaluated is zero. Do not imply alpha.

## 3. In-scope requirements

### R1. Stacked count bar

The morning detail MUST include `#funnel-bars`. When
`n_evaluated + n_passed + n_failed + n_incomplete > 0`, JS MUST
render a `.funnel-stack` whose segments are:

| `data-key` | count | color token |
| --- | --- | --- |
| `passed` | `n_passed` | `--accent` |
| `failed` | `n_failed` | `--warn` |
| `incomplete` | `n_incomplete` | `--inconclusive` |

Each `.funnel-seg` MUST set `data-pct` to the integer percent of
`max(n_evaluated, 1)` and `style.width` to that percent. Always
emit all three keys so the encoding is stable. `#funnel-summary`
MUST still show `evaluated`, `passed`, and `failed`, and MUST also
show `incomplete`.

When every count is zero, `#funnel-bars` stays empty (no stack).
Do not invent a filled bar.

### R2. Dominant-failure bars

`#funnel` items for named failures MUST keep `name × n` text and
MUST include a track whose fill width is `count / max(n_failed, 1)`
percent, exposed as `data-pct` on `.funnel-fail-fill`. Empty list
MAY still render `none`.

### R3. Locks

`HOST_CONSTRAINT` text unchanged. Help sentences unchanged. Example
YAML unchanged. No `FakeWorker` in morning e2e. No gate override.
No invented `FOUND`. Packaged page only (`src/alphaloop/webui/static/`).

## 4. Out of scope

- Textbook `S=16` CPCV. Soak / 95% overnight as CI.
- Correlation-adjusted \(N_{\mathrm{eff}}\).
- Job-list mini-bars (later). Unfreezing `webui/`. MCP / cloud workers.

## 5. Acceptance

- Unit (packaged assets): HTML has `#funnel-bars`; JS writes
  `.funnel-stack`, `.funnel-seg`, `data-pct`, and `incomplete:`;
  CSS defines `.funnel-stack` and outcome-colored segments.
  `HOST_CONSTRAINT` still matches `preflight.HOST_CONSTRAINT`.
- E2E: job detail includes `#funnel-bars`. After a terminal job,
  `.funnel-stack .funnel-seg[data-key="passed"]` is present with
  `data-pct`. Chromium matrix still passes. Do not invent `FOUND`.

## 6. Loop exit

Remaining validation: textbook `S=16` CPCV, soak / 95% overnight
(release process, not CI), correlation-adjusted \(N_{\mathrm{eff}}\).
Remaining product after this cycle shipped: overnight search
progress (`docs/requirements/2026-08-20-search-progress.md`).
Remaining validation: textbook `S=16` CPCV, soak / 95% overnight
(release process, not CI), correlation-adjusted \(N_{\mathrm{eff}}\).
Remaining later: job-list mini-funnel, MCP / cloud workers.
