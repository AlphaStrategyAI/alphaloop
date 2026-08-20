---
title: "Morning evidence lines use the same hard-gate gloss as the form"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-hard-gate-glosses.md / 2026-08-20-primary-evidence.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-hard-gate-glosses.md
  - docs/requirements/2026-08-20-primary-evidence.md
---

# Morning evidence lines use the same hard-gate gloss as the form

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `format_gate_line`, `format_primary_evidence` missing/failure
names, and packaged `#evidence` / `#primary-evidence` which render
those strings. Not a new hard gate. Not inventing `FOUND`. Not
changing checkbox `value`s. Not unfreezing `webui/`. Not soak. Not
\(N_{\mathrm{eff}}\). Not restyling chrome. Not changing queued
hypothesis prose.

## 1. Why this cycle exists

PRD §3.4 / §4.3: a five-minute reader identifies conclusion, **primary
evidence**, and stop reason from the home page. Hard-gate glosses
already teach the one-minute form `dsr — Deflated Sharpe Ratio`.
Morning `#evidence` and `primary_evidence` still print `dsr: fail` and
`dsr failed`. The freeze vocabulary and the morning vocabulary disagree.
Nielsen: recognition rather than recall. CONSORT: the primary result
should be readable next to the conclusion.

Detail keys (`n_trials=`, `regime_stable=`) stay machine tokens. This
cycle glosses **gate names** only.

## 2. Best-practice basis

1. **Same locked gloss as the form.** `HARD_GATE_GLOSS` MUST match
   `docs/requirements/2026-08-20-hard-gate-glosses.md` R2 exactly.
2. **Keep the token first.** Gloss text still starts with the
   `HardGateName` value so YAML authors recognize it.
3. **Do not claim alpha.** MUST NOT print `FOUND` as a gate gloss.
4. **Unknown names stay raw.** A name not in `HardGateName` MUST be
   printed unchanged (no invented em dash).
5. **Do not shrink N.** Detail `n_trials=` is still unique-ledger N.

## 3. In-scope requirements

### R1. Shared map

`alphaloop.contracts.gates` MUST export `HARD_GATE_GLOSS` mapping every
`HardGateName.value` to the locked label, and `gloss_hard_gate(name)`
returning that label or the raw name.

### R2. Evidence lines

`format_gate_line` MUST use `gloss_hard_gate(name)` before `: pass` /
`: fail`. Example:

`dsr — Deflated Sharpe Ratio: pass`

Detail key=value tails stay unchanged.

### R3. Primary evidence

When `format_primary_evidence` interpolates a gate name:

- NO_EVIDENCE with a dominant failure: `{gloss} failed`
- INCONCLUSIVE missing required names: `missing {gloss, ...}`

FOUND / empty-dominant / `no sealed gates.json` / `incomplete evidence
set` sentences stay locked as today.

### R4. Console and report

`#evidence` still renders `evidence_lines`. `#primary-evidence` still
renders `primary_evidence`. `report.md` uses the same formatters. No
JS gloss table.

### R5. Docs

`docs/webui.md` MUST say morning evidence lines use the same hard-gate
gloss as the form.

## 4. Out of scope

- Gloss detail keys. Queued hypothesis statements. Soak.
  \(N_{\mathrm{eff}}\). Unfreezing `webui/`. New gates.

## 5. Acceptance

- Unit: `format_gate_line` empty-detail `dsr` is
  `dsr — Deflated Sharpe Ratio: pass`.
- Unit: NO_EVIDENCE dominant `dsr` primary evidence is
  `dsr — Deflated Sharpe Ratio failed`.
- Unit: unknown name `custom: pass`.
- Packaged checkboxes still contain every `HARD_GATE_GLOSS` value.
- E2E walk-forward job `#evidence` contains `walk-forward OOS`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
