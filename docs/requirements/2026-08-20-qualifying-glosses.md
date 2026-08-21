---
title: "Qualifying candidate kinds use the same signal gloss as the form"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-qualifying-candidates.md / 2026-08-20-preview-followup-gloss.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-qualifying-candidates.md
  - docs/requirements/2026-08-20-found-handoff.md
  - docs/requirements/2026-08-20-preview-followup-gloss.md
  - docs/requirements/2026-08-20-signal-families.md
---

# Qualifying candidate kinds use the same signal gloss as the form

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Morning `#qualifying` / `#handoff` kind display,
`report.md` qualifying rows, CLI `format_status_verdict` qualifying
line, and an additive `kind_label` on each qualifying-candidate
object. Not a new DSL kind. Not inventing `FOUND`. Not auto-export.
Not changing `kind` tokens. Not unfreezing `webui/`. Not soak. Not
\(N_{\mathrm{eff}}\). Not restyling chrome.

## 1. Why this cycle exists

PRD §4.3: after the conclusion, name **qualifying candidates and
supporting evidence**. The one-minute form and freeze preview already
print `momentum_12_1 — 12-1 momentum`. Surviving-candidate rows still
print the raw DSL token. Nielsen: recognition rather than recall.
CONSORT: the analysed set that met the predeclared criteria should
use the same names the protocol preview taught.

`kind` stays the ledger token so export and Load keep a stable
identifier. This cycle glosses **display** only.

## 2. Best-practice basis

1. **Same locked signal gloss as the form**
   (`SIGNAL_GLOSS` / `gloss_signal` from
   `2026-08-20-signal-families.md` R3 /
   `2026-08-20-preview-followup-gloss.md` R1). Feature/volume kinds
   are not in the map; `gloss_signal` returns the raw name.
2. **Keep the token first.** Gloss text still starts with the DSL
   kind.
3. **Do not rename payload `kind`.** Export, ledger join, and
   `signal_mechanism` stay tokens.
4. **Do not claim alpha.** A glossed qualifying row is not `FOUND`.
5. **Unknown / missing kinds stay raw or empty.** `kind` `None`
   (last-only `gates.json` fallback) has `kind_label` `None`.
6. **No JS gloss table.** Packaged JS MUST render `kind_label` when
   present, else `kind`.

## 3. In-scope requirements

### R1. Additive `kind_label`

`_qualifying_entry` / `build_qualifying_candidates` MUST add
`kind_label`: `gloss_signal(kind)` when `kind` is a non-empty
string, else `None`. Existing `trial_id`, `kind`, `parameters` stay.

### R2. Report

`write_report` qualifying rows MUST interpolate `kind_label` when
present, else `kind`. Format stays
`{trial_id} · {label} · {parameters}`. Empty list remains `none`.

### R3. Console and CLI status

`#qualifying` and `#handoff` MUST show `kind_label` when present,
else `kind`. `format_status_verdict` FOUND qualifying line MUST use
the same fallback. Export receipt `Qualifying: {candidate_id}` (no
kind) stays locked. Empty qualifying MAY still render `none`.

### R4. Docs

`docs/webui.md` MUST say qualifying candidate kinds use the same
signal gloss as the form. Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC
stay locked.

## 4. Out of scope

- Auto-export. Gloss revision `method` lines. Soak.
  \(N_{\mathrm{eff}}\). Unfreezing `webui/`. New kinds. Changing
  export receipt shape.

## 5. Acceptance

- Unit: a passing trial with ledger `kind` `momentum_12_1` keeps
  `kind == "momentum_12_1"` and
  `kind_label == "momentum_12_1 — 12-1 momentum"`.
- Unit: last-only `gates.json` row still has `kind` / `kind_label`
  `None`.
- Unit: `format_status_verdict` FOUND line contains `12-1 momentum`
  when `kind_label` is present; missing `kind_label` still falls
  back to `kind`.
- Packaged JS reads `kind_label`. No `SIGNAL_GLOSS` in `app.js`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
