---
title: "Morning console — example spec, in-page control, and a scannable overnight layout"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-protocol-preview.md
  - docs/requirements/2026-08-20-honest-docs-morning-help.md
---

# Morning console — example spec, in-page control, and a scannable overnight layout

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged static morning page (`src/alphaloop/webui/static/`)
interaction and visual design. Not the frozen Vite SPA. Not CPCV. Not
a trading UI.

## 1. Why this cycle exists

The product goal is a **verifiable, explorable, easy, visually
distinct, intuitively interactive** overnight research lab. PRD §3.4
and §4.3 require a five-minute morning read. PRD §4.1 requires a
one-minute submit. PRD §5.1–5.2 require the Web console to create,
cancel, resume, and inspect jobs. Nielsen's **recognition rather than
recall** says users should not have to remember YAML keys
([NN/g heuristic 6](https://www.nngroup.com/articles/ten-usability-heuristics/)).
**Visibility of system status** says running vs sealed must stay
visible ([NN/g heuristic 1](https://www.nngroup.com/articles/visibility-system-status/)).
Tufte: the display must not imply a claim the evidence does not
support.

Today the packaged page is a blank YAML box, a job list of opaque
ids, and Georgia body text. There is no example hypothesis, no
cancel/resume on the page (CLI only), and no layout that separates
"before bed" from "next morning." That is the largest remaining gap
versus the product goal that is still first-release sized.

## 2. In-scope requirements

### R1. Example spec (recognition)

`#load-example` fills `#spec-yaml` with this YAML, verbatim, including
the trailing newline:

```yaml
statement: 12-1 momentum works in US large caps net of costs
economic_logic: past winners continue
signal_mechanism: momentum_12_1
market_scope: AAPL, MSFT
market_profile: us-equity-daily
benchmark: SPY
hard_gates: [dsr, walk_forward, vs_benchmark]
seed: 7
time_budget_s: 3600
cost_budget_usd: 5.0
```

Filling MUST fire the same `input` path as typing so Freeze stays
disabled until Preview succeeds. The button MUST NOT invent `FOUND`
and MUST NOT POST a job.

### R2. In-page cancel and resume

When a job is open in `#detail`:

- `#cancel-job` is visible iff status is `queued` or `running`.
  Click POSTs `/v1/jobs/{run_id}/cancel` and refreshes detail + list.
- `#resume-job` is visible iff status is `failed`.
  Click POSTs `/v1/jobs/{run_id}/resume` and refreshes detail + list.
- Both hidden otherwise. Neither overrides gates.

### R3. Scannable overnight layout

At viewport width ≥ 56rem, `#before-bed` (submit/preview) and
`#morning` (jobs + detail) sit in two columns. Below that, they
stack. Existing element ids stay.

Job list buttons KEEP exact `textContent`:

```text
{run_id} — {status} — {research_outcome}
```

They MAY set `data-status` and `data-outcome` for styling.

`#protocol-preview` inner text MUST still contain `planned_n_trials`
after a successful parse.

`#outcome` remains the visual lead of detail. Status stays on
`#job-status`. Distinct outcome colors stay. `FOUND` stays the existing
accent green; the others MUST NOT share that green.

### R4. Visual system (packaged CSS only)

Restyle `styles.css` so the page reads as a research console, not a
blank document:

- System UI + monospace (no webfont fetch).
- Card surfaces for jobs, preview, and detail.
- Focus-visible rings on buttons and the textarea.
- Left accent on a job button from `data-outcome` (FOUND / NO_EVIDENCE /
  INCONCLUSIVE / NONE), never using FOUND green for the other three.

No Node. No unfreezing `webui/`. No gate override.

### R5. Docs

`docs/webui.md` first-release lead mentions: load example, preview,
freeze, cancel/resume on the page.

## 3. Out of scope

- Vite SPA, live trading, CPCV, new DSL kinds.
- Changing locked `HOST_CONSTRAINT` or help sentences.
- Changing CLI submit into a wizard.
- FakeWorker in morning e2e.
- Inventing `FOUND`.

## 4. Acceptance

- Unit: HTML/JS contain `#load-example`, example YAML string,
  `/cancel`, `/resume`; submit starts disabled; list format unchanged.
- Integration: daemon still serves `/`; cancel/resume HTTP unchanged.
- E2E: load example fills the textarea; preview does not create a job;
  cancel from the page before seal is `INCONCLUSIVE`; legal outcomes
  only.
