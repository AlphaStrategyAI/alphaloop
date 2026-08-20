---
title: "Morning elimination funnel across the frozen grid"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.3"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-19-five-minute-morning-review.md
  - docs/requirements/2026-08-20-frozen-grid-honest-kinds.md
---

# Morning elimination funnel across the frozen grid

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Per-trial sealed evidence plus a search-wide elimination
funnel on the morning payload, packaged console, and `report.md`.
Not a new `HardGateName`. Not `S=16`. Not soak. Not inventing `FOUND`.

## 1. Why this cycle exists

PRD §4.3 requires the morning page to lead with one conclusion, then:

1. qualifying candidates and supporting evidence;
2. **the candidate elimination funnel and dominant failure reasons**;
3. methodological revisions;
4. queued future hypotheses.

Five-minute review (PRD §3.4) is a first-release success criterion.
Bailey / López de Prado: the reader must see **what was tried** and
**how it died** before trusting a surviving Sharpe.

The frozen-grid cycle now evaluates every predeclared method point
after a complete fail. `gates.json` is still **last trial only**.
`morning_view.funnel.dominant_failures` is therefore the last
candidate's failed gates, not the search funnel. After three momentum
points all miss DSR, the page can look like a one-trial fail. That
makes `planned_n_trials` honest in preview and dishonest in the
morning.

## 2. Best-practice basis

1. **CONSORT / pre-registration:** report the full evaluated set, not
   the last observation.
2. **Nielsen visibility of system status:** counts (evaluated / passed
   / failed) before a list of names.
3. **Tufte:** do not imply a one-shot verdict when a grid was walked.
   Do not claim alpha.

## 3. In-scope requirements

### R1. Per-trial sealed evidence

Whenever `run_protocol` writes complete `GateEvidence` to
`evidence/gates.json`, it MUST also write the same JSON to
`evidence/trials/{candidate_id}.json`. Incomplete trials MUST NOT
create a trial file (do not invent gates). After PBO attach rewrites
`gates.json`, the matching trial file MUST be rewritten too.

### R2. Funnel payload

`morning_view` `funnel` MUST include:

| Key | Meaning |
| --- | --- |
| `n_evaluated` | unique ledger `trial_id`s, or `n_complete` when the ledger is empty but last/`trials` evidence exists |
| `n_complete` | complete evidence sets (trial files, else last `gates.json`) |
| `n_passed` | complete and `all_passed` |
| `n_failed` | complete and not `all_passed` |
| `n_incomplete` | `max(0, n_evaluated - n_complete)` |
| `failure_counts` | map of required gate name → how many complete failing trials failed that gate |
| `dominant_failures` | those names sorted by count descending, then name ascending; empty if none |

Existing last-only `dominant_failures` for a single `gates.json` and no
trial files MUST stay the failed required gates of that last set
(backward compatible).

### R3. Console

`#funnel-summary` MUST show `evaluated`, `passed`, and `failed` counts
from the payload. `#funnel` list items for named failures MUST include
the count (`dsr × 3`). Empty failure list MAY still render `none`.
Revision rows SHOULD include parameters via the existing grid-row
formatter so a five-minute reader sees what was tried. No gate
override. No invented `FOUND`. `HOST_CONSTRAINT` unchanged.

### R4. `report.md`

When `n_evaluated > 0` or `n_complete > 0`, `write_report` MUST include
an `## Elimination funnel` section with the same counts and
`name: count` lines for `dominant_failures`. Still a view of evidence,
not a source of truth. Locked no-alpha sentence unchanged.

## 4. Out of scope

- New YAML gate. Textbook `S=16`. Soak. FakeWorker in morning e2e.
- In-run LLM proposer. Volume parquet. Unfreezing `webui/`.

## 5. Acceptance

- Unit: three complete fails write three trial files; funnel
  `n_failed == 3` and `failure_counts` sums the grid, not only the
  last trial.
- Unit: last-only `gates.json` (no `trials/`) still fills
  `dominant_failures` as today.
- Unit: report contains `## Elimination funnel` when trials exist.
- Packaged HTML has `#funnel-summary`; JS reads `failure_counts`.
- E2E: job detail `#funnel-summary` contains `evaluated:`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
