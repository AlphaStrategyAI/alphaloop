---
title: "CLI status names the elimination funnel"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-cli-status-verdict.md / 2026-08-20-funnel-glosses.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-cli-status-verdict.md
  - docs/requirements/2026-08-20-funnel-glosses.md
  - docs/requirements/2026-08-20-status-revision-gloss.md
---

# CLI status names the elimination funnel

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `format_status_verdict` optional `Funnel:` / `Dominant:`
lines from `view["funnel"]`; `replay_view` includes the same `funnel`
object as `morning_view`. Not inventing `FOUND`. Not shrinking DSR
`N`. Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\).
Not restyling chrome. Not changing funnel JSON keys.

## 1. Why this cycle exists

PRD §4.3 / §10.2: after the conclusion, present **the candidate
elimination funnel and dominant failure reasons**. The packaged
morning page already draws `#funnel-bars` with gate glosses.
`report.md` already has `## Elimination funnel`. `alphaloop status`
still omits those counts, so a five-minute terminal reader cannot see
how the frozen grid died without `--json` or opening the report.

Nielsen: visibility of system status. CONSORT: name the analysed
denominator (`n_evaluated`) and why candidates failed. Failure count
keys stay tokens (`dsr`); printed names use `dominant_failure_labels`.

YAML / EXAMPLE_SPEC / Help / `HOST_CONSTRAINT` unchanged.

## 2. Best-practice basis

1. **Same payload as morning.** Read `view["funnel"]`. Do not
   recompute gates in the formatter.
2. **Keep the cluster compact.** One `Funnel:` summary line, then one
   `Dominant:` line per `dominant_failures` entry using the matching
   `dominant_failure_labels` gloss (fallback: raw name).
3. **Empty omits.** When `n_evaluated`, `n_passed`, `n_failed`, and
   `n_incomplete` are all zero or `funnel` is missing, omit every
   `Funnel:` / `Dominant:` line.
4. **Do not claim alpha.** Locked outcome gloss and no-alpha sentence
   unchanged. Do not print `FOUND` from empty counts.

## 3. In-scope requirements

### R1. Verdict lines

`format_status_verdict` MUST, after `Stop reason:` and before
`Revision:` / `Next run:`, emit:

- `Funnel: evaluated={n} passed={n} failed={n} incomplete={n}` when
  any of those counts is nonzero
- `Dominant: {label} × {count}` for each `dominant_failures` name, in
  that list's order, using `dominant_failure_labels[i]` when present
  else the raw name, and `failure_counts[name]`

### R2. Replay payload

`replay_view` MUST include `funnel` from `build_funnel(layout)`.
`--json` already dumps the view; do not invent `FOUND`.

### R3. Docs

`docs/cli.md` MUST say the five-minute cluster may include funnel
counts and dominant-failure glosses. Help / `HOST_CONSTRAINT` /
EXAMPLE_SPEC stay locked.

## 4. Out of scope

- Funnel bar charts on CLI. Changing Web `#funnel-bars`. Soak.
  \(N_{\mathrm{eff}}\). Unfreezing `webui/`. Rewriting the ledger.

## 5. Acceptance

- Unit: funnel with `n_evaluated=3`, `n_failed=3`, `dsr: 3` prints
  `Funnel: evaluated=3 passed=0 failed=3 incomplete=0` and
  `Dominant: dsr — Deflated Sharpe Ratio × 3`.
- Unit: missing/zero funnel omits `Funnel:` and `Dominant:`.
- Unit: `replay_view` includes `funnel` as a mapping.
- E2E: human `alphaloop status RUN_ID` contains `Funnel:` when the
  JSON payload's `funnel.n_evaluated` is nonzero.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
