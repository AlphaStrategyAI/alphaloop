---
title: "Preview and queued follow-ups use locked signal and gate glosses"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-signal-families.md / 2026-08-20-evidence-glosses.md / 2026-08-20-queued-followup.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-signal-families.md
  - docs/requirements/2026-08-20-hard-gate-glosses.md
  - docs/requirements/2026-08-20-cli-preview-seed.md
  - docs/requirements/2026-08-20-queued-followup.md
---

# Preview and queued follow-ups use locked signal and gate glosses

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Canonical `SIGNAL_GLOSS` / `gloss_signal`; protocol preview
(CLI + packaged card); `followup_hypotheses` statement text; additive
`signal_label` / `hard_gate_labels` on `preview_run`. Not a new DSL
kind. Not inventing `FOUND`. Not auto-executing the queued hypothesis.
Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not
changing YAML `signal_mechanism` values. Not restyling chrome.

## 1. Why this cycle exists

The one-minute form already shows `momentum_12_1 — 12-1 momentum` and
`dsr — Deflated Sharpe Ratio`. Freeze review (`#protocol-preview` /
`alphaloop preview`) still prints tokens. The overnight lab queues a
counterpart after `NO_EVIDENCE` (`Try rsi`) so a human can iterate;
that sentence also uses tokens. PRD §4.1 review-before-freeze and
§4.3 / §6.1 evidence-backed next hypothesis both fail recognition.
Nielsen: the freeze card and the next-run cue must name the same
economic kinds the form already taught.

YAML, Load example, and `signal_mechanism` JSON values stay tokens.

## 2. Best-practice basis

1. **Same locked signal gloss as the form**
   (`2026-08-20-signal-families.md` R3). Features/volume kinds are
   not in the map; `gloss_signal` returns the raw name.
2. **Same locked gate gloss** (`HARD_GATE_GLOSS`) for preview gate
   lists and follow-up dominant-failure names.
3. **Keep the token first.** `signal_mechanism:` still starts the
   line; the gloss follows.
4. **Do not execute the follow-up.** `signal_mechanism` on the queued
   object stays the DSL kind. Human Load + Freeze still required.
5. **Do not claim alpha.** Follow-up still contains
   `This is not a claim of alpha.`

## 3. In-scope requirements

### R1. `SIGNAL_GLOSS`

`alphaloop.protocol.dsl` MUST export `SIGNAL_GLOSS` for every
`DIRECTIONAL_SIGNAL_KINDS` entry (locked table from signal-families
R3) and `gloss_signal(kind) -> str`.

### R2. Preview payload

`preview_run` MUST add:

- `signal_label`: `gloss_signal(signal_mechanism)`
- `hard_gate_labels`: `[gloss_hard_gate(name) for name in hard_gates]`

Existing keys unchanged. No `run_id`.

### R3. Human preview

`format_protocol_preview` MUST print glossed signal and gates.
Packaged `renderPreview` MUST use `signal_label` / `hard_gate_labels`
when present (fallback: raw keys).

### R4. Follow-up statement

`followup_hypotheses` statement MUST interpolate `gloss_signal(kind)`,
`gloss_signal(nxt)`, and `gloss_hard_gate` on dominant failed names.
`signal_mechanism` on the queued dict stays `nxt` (token).

### R5. Docs

`docs/webui.md` / `docs/cli.md` MUST note preview names the signal
gloss. Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC stay locked.

## 4. Out of scope

- Auto-submit of queued follow-ups. Funnel payload key rename. Soak.
  \(N_{\mathrm{eff}}\). Unfreezing `webui/`. New kinds.

## 5. Acceptance

- Unit: `gloss_signal("momentum_12_1")` is the locked label; unknown
  kind unchanged.
- Unit: `format_protocol_preview` contains `12-1 momentum` and
  `Deflated Sharpe Ratio`.
- Unit: `followup_hypotheses` statement contains those glosses;
  `signal_mechanism == "rsi"`.
- Static: every `SIGNAL_GLOSS` value appears in `#field-signal-mechanism`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
