---
title: "Morning qualifying candidates from sealed trial evidence"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.3"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-morning-funnel.md
  - docs/requirements/2026-08-20-morning-lead.md
---

# Morning qualifying candidates from sealed trial evidence

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Name the candidates that actually passed every required
hard gate, from per-trial sealed evidence, on `morning_view`, the
packaged console, and `report.md`. Not a new `HardGateName`. Not
inventing `FOUND`. Not unfreezing `webui/`.

## 1. Why this cycle exists

PRD §4.3 order after the conclusion is:

1. **qualifying candidates and supporting evidence**
2. elimination funnel
3. methodological revisions
4. queued future hypotheses

The funnel cycle counts `n_passed`. The page still has no list of
*who* passed. A five-minute reader who sees `FOUND` cannot tell
which frozen-grid point survived; a `NO_EVIDENCE` reader cannot
confirm that the qualifying set is empty. Bailey / López de Prado:
report the survivors of the search, not only the last Sharpe.

`docs/requirements/2026-08-20-morning-lead.md` closed auto-open.
This cycle takes the still-missing §4.3(1) named surface.

## 2. Best-practice basis

1. **CONSORT / pre-registration:** name the analysed set that met
   the predeclared criteria.
2. **Do not invent `FOUND`:** a non-empty qualifying list is a view
   of complete `all_passed` evidence, not a second outcome channel.
3. **Last-only fallback:** when `evidence/trials/` is absent, a
   complete passing `gates.json` still counts as one unlabeled
   sealed set (`trial_id` `gates.json` if the ledger is empty).

## 3. In-scope requirements

### R1. Payload

`morning_view` MUST include `qualifying_candidates`: a list of
objects `{trial_id, kind, parameters}` for every complete
`all_passed` trial file under `evidence/trials/`, joined to the
trial ledger for `kind` / `parameters` when present. Sort by
filename. Failed or incomplete trials MUST NOT appear.

When there are no trial files, if last `gates.json` is complete
and `all_passed`, emit one row: ledger last `trial_id` if any,
else `trial_id` `"gates.json"`. Otherwise the list is empty.
`NO_EVIDENCE` / missing gates → empty list. Do not mark
`research_outcome` from this list.

### R2. Console and report

Packaged detail MUST include `#qualifying` **before** `#evidence`.
Rows render `trial_id · kind · parameters` via the existing grid
formatter. Empty list MAY render `none`.

`report.md` MUST include `## Qualifying candidates` with the same
rows, or `none`. Locked no-alpha sentence unchanged.

### R3. Locks

`HOST_CONSTRAINT` unchanged. Help sentences unchanged. Example YAML
unchanged. No `FakeWorker` in morning e2e. No gate override.

## 4. Out of scope

- Textbook `S=16`. Soak. \(N_{\mathrm{eff}}\). MCP / cloud workers.
- Auto-running queued economic follow-ups. Unfreezing `webui/`.

## 5. Acceptance

- Unit: last-only passing `gates.json` → one qualifying row;
  last-only failing `gates.json` → `[]`; mixed trial files → only
  the `all_passed` ids.
- Report contains `## Qualifying candidates`.
- Packaged HTML has `#qualifying`; JS reads `qualifying_candidates`.
- E2E: job detail includes `#qualifying`. Do not invent `FOUND`.

## 6. Loop exit

Remaining validation: textbook `S=16` CPCV, soak / 95% overnight
(not CI), correlation-adjusted \(N_{\mathrm{eff}}\). Later: MCP /
cloud workers.
