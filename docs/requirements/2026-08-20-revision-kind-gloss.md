---
title: "Methodological revisions name the repaired signal kind"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-honest-revisions.md / 2026-08-20-qualifying-glosses.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-honest-revisions.md
  - docs/requirements/2026-08-20-qualifying-glosses.md
  - docs/requirements/2026-08-20-preview-followup-gloss.md
---

# Methodological revisions name the repaired signal kind

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Additive `kind_label` on `morning_view["revisions"]` rows;
packaged `#revisions` line format; `report.md` `## Methodological
revisions` section via `format_revision_line`. Not a new revision
kind. Not inventing `FOUND`. Not changing `trial-ledger.jsonl`. Not
shrinking DSR `N`. Not moving economic ideas into `#revisions`. Not
unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not restyling
chrome.

## 1. Why this cycle exists

PRD §4.3: after the funnel, show **methodological revisions made
during the run**. Qualifying rows already print
`momentum_12_1 — 12-1 momentum`. `#revisions` still prints
`c_2 · method · window=21`. The ledger already stores `kind`. A
five-minute reader cannot tell which frozen signal the method repair
applied to. Nielsen: recognition rather than recall. CONSORT: name
the analysed method, not only an internal revision token.

`revision: "method"` stays the filter. Unique-ledger `n_trials` stays
full-ledger N. YAML / EXAMPLE_SPEC unchanged.

## 2. Best-practice basis

1. **Same locked signal gloss as the form** (`gloss_signal`).
2. **Keep the revision token.** Lines still include `method` so the
   heading matches the ledger field.
3. **Do not rewrite the ledger.** Additive `kind_label` on the view
   only.
4. **Empty is honest.** No method rows → `#revisions` / report section
   `none`. MUST NOT print `FOUND`.
5. **Unknown / missing kinds stay raw or omitted.** `kind` missing →
   `kind_label` `None`; the line omits an empty kind slot.
6. **No JS gloss table.** Packaged JS MUST render `kind_label` when
   present, else `kind`.

## 3. In-scope requirements

### R1. Additive `kind_label`

`build_method_revisions` / `_load_revisions` MUST copy each
`revision == "method"` ledger row and set `kind_label` to
`gloss_signal(kind)` when `kind` is a non-empty string, else `None`.
Existing ledger keys stay. Filter unchanged.

### R2. Line format

`format_revision_line(row)` MUST join, with ` · `, the non-empty
values among `trial_id`, `revision`, `kind_label` (else `kind`), then
the existing grid-row parameters (`{}` when empty).

`#revisions` MUST use that line. Empty list MAY still render `none`.

### R3. Report

`write_report` MUST include `## Methodological revisions` after
qualifying candidates, with `format_revision_line` rows or `none`.
Locked no-alpha sentence unchanged.

### R4. Docs

`docs/webui.md` MUST say methodological revision lines name the
repaired signal with the same gloss as the form. Help /
`HOST_CONSTRAINT` / EXAMPLE_SPEC stay locked.

## 4. Out of scope

- New revision kinds. Changing ledger writes. Soak.
  \(N_{\mathrm{eff}}\). Unfreezing `webui/`. CLI status revision
  lines. Queued economic hypotheses.

## 5. Acceptance

- Unit: method row with `kind` `momentum_12_1` keeps
  `revision == "method"` and
  `kind_label == "momentum_12_1 — 12-1 momentum"`; `n_trials`
  still counts `none` rows.
- Unit: `format_revision_line` is
  `c_2 · method · momentum_12_1 — 12-1 momentum · window=21`.
- Unit: report contains `## Methodological revisions` and that line.
- Packaged revisions renderer reads `kind_label`. No `SIGNAL_GLOSS`
  in `app.js`.
- E2E bollinger job: when the ledger has a `method` row, `#revisions`
  contains `Bollinger z-score`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
