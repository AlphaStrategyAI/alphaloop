---
title: "Elimination funnel names use the same hard-gate gloss as the form"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-morning-funnel.md / 2026-08-20-evidence-glosses.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-morning-funnel.md
  - docs/requirements/2026-08-20-funnel-bars.md
  - docs/requirements/2026-08-20-evidence-glosses.md
  - docs/requirements/2026-08-20-hard-gate-glosses.md
---

# Elimination funnel names use the same hard-gate gloss as the form

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Morning `#funnel` list labels, `report.md` elimination
lines, and an additive `dominant_failure_labels` list on the funnel
payload. Not a new hard gate. Not inventing `FOUND`. Not renaming
`failure_counts` keys or `dominant_failures` tokens. Not unfreezing
`webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not restyling chrome.
Not glossing qualifying `kind` or handoff lines.

## 1. Why this cycle exists

PRD §3.4 / §4.3: a five-minute reader identifies the conclusion, then
the **candidate elimination funnel and dominant failure reasons**.
Evidence lines already print `dsr — Deflated Sharpe Ratio: fail`.
The funnel list and `report.md` still print `dsr × 3` / `dsr: 3`.
The freeze vocabulary, the evidence vocabulary, and the funnel
vocabulary disagree. Nielsen: recognition rather than recall.
CONSORT: the elimination record should name the same pre-specified
gates the form already taught.

Payload keys stay machine tokens so DSR `N` and aggregators keep a
stable map. This cycle glosses **display** only.

## 2. Best-practice basis

1. **Same locked gloss as the form.** `HARD_GATE_GLOSS` / `gloss_hard_gate`
   from `docs/requirements/2026-08-20-hard-gate-glosses.md` R2 and
   `docs/requirements/2026-08-20-evidence-glosses.md` R1.
2. **Keep the token first.** Gloss text still starts with the
   `HardGateName` value so YAML authors recognize it.
3. **Do not rename payload keys.** `failure_counts` keys and
   `dominant_failures` entries MUST remain enum tokens (`dsr`,
   `walk_forward`, …).
4. **Do not claim alpha.** MUST NOT print `FOUND` as a funnel gloss.
5. **Unknown names stay raw.** A name not in `HardGateName` MUST be
   printed unchanged (no invented em dash).
6. **Do not shrink N.** Funnel `n_evaluated` is still unique-ledger N.
7. **No JS gloss table.** Packaged JS MUST render server-provided
   labels, not a second copy of `HARD_GATE_GLOSS`.

## 3. In-scope requirements

### R1. Additive labels

`build_funnel` MUST add `dominant_failure_labels`: a list of
`gloss_hard_gate(name)` in the same order as `dominant_failures`.
Existing keys stay. Empty `dominant_failures` yields an empty labels
list.

### R2. Report lines

`write_report` elimination lines MUST be
`{gloss_hard_gate(name)}: {count}` for each `dominant_failures`
entry. Counts, `evaluated` / `passed` / `failed` totals, and the
locked no-alpha sentence stay unchanged.

### R3. Console

`#funnel` items for named failures MUST show
`{label} × {count}` where `label` is
`dominant_failure_labels[i]` when present, else the raw
`dominant_failures[i]` token. Track fill, `data-pct`, and
`#funnel-summary` counts stay as `2026-08-20-funnel-bars.md`. Empty
list MAY still render `none`.

### R4. Docs

`docs/webui.md` MUST say the elimination funnel uses the same
hard-gate gloss as the form. Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC
stay locked.

## 4. Out of scope

- Gloss qualifying `kind` / handoff lines. Gloss detail keys. Soak.
  \(N_{\mathrm{eff}}\). Unfreezing `webui/`. New gates. Renaming
  `failure_counts` keys.

## 5. Acceptance

- Unit: `build_funnel` / `morning_view` keep `dominant_failures[0]
  == "dsr"` and `failure_counts["dsr"]`; `dominant_failure_labels[0]`
  is `dsr — Deflated Sharpe Ratio`.
- Unit: `report.md` contains `dsr — Deflated Sharpe Ratio: 1` and MUST
  NOT contain a bare `dsr: 1` elimination line.
- Packaged JS reads `dominant_failure_labels`. No second gloss map
  in `app.js`.
- E2E walk-forward job: `#funnel` MUST NOT contain `walk_forward ×`;
  when the list is not `none`, it MUST contain `walk-forward OOS`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
