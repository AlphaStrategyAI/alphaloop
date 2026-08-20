---
title: "Hard-gate checkboxes keep the token and a human gloss"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-guided-spec-form.md / 2026-08-20-signal-families.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-guided-spec-form.md
  - docs/requirements/2026-08-20-signal-families.md
---

# Hard-gate checkboxes keep the token and a human gloss

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged `#field-hard-gates` checkbox labels. Not a new
hard gate. Not inventing `FOUND`. Not changing checkbox `value`s or
YAML. Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\).
Not restyling chrome. Not changing morning evidence lines.

## 1. Why this cycle exists

PRD §4.1 is a one-minute submit: choose gates, preview, freeze.
Guided-spec-form already lists every `HardGateName` as a checkbox
`value`. Visible text is still the machine token (`dsr`,
`walk_forward`). Signal families just added an em-dash gloss so the
researcher recognizes the economic family. Hard gates are the other
frozen choice that decides `FOUND`. Nielsen: recognition rather than
recall. Bailey / López de Prado: the user should know they are
freezing Deflated Sharpe and walk-forward OOS, not opaque YAML keys.

`value` stays the enum token. YAML, preview, Load example, and
evidence lines stay unchanged. This cycle is the visible gloss.

## 2. Best-practice basis

1. **Keep the token in the label.** Visible text MUST contain the
   checkbox `value` so YAML authors still recognize it.
2. **Same em-dash pattern as signals.** Non-empty labels use ` — `
   after the token.
3. **Do not claim alpha.** Labels MUST NOT say a gate finds alpha or
   promises profitability.
4. **Do not add gates.** MUST NOT invent a seventh checkbox.

## 3. In-scope requirements

### R1. Values

`#field-hard-gates` checkbox `value`s remain exactly every
`HardGateName` (`dsr`, `walk_forward`, `vs_random`, `vs_buy_hold`,
`vs_benchmark`, `data_consistency`). Form JS still reads `.value`.

### R2. Human gloss

Each checkbox label's visible text MUST be:

| value | visible text |
| --- | --- |
| `dsr` | `dsr — Deflated Sharpe Ratio` |
| `walk_forward` | `walk_forward — walk-forward OOS` |
| `vs_random` | `vs_random — versus random` |
| `vs_buy_hold` | `vs_buy_hold — versus buy-and-hold` |
| `vs_benchmark` | `vs_benchmark — versus benchmark` |
| `data_consistency` | `data_consistency — data consistency` |

### R3. Docs

`docs/webui.md` MUST name that hard-gate checkboxes keep the token
plus a human gloss. Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC stay
locked.

## 4. Out of scope

- Changing morning `#evidence` lines (still machine tokens).
- Auto-checking gates. Soak. \(N_{\mathrm{eff}}\). Unfreezing
  `webui/`. New gate kinds.

## 5. Acceptance

- Static: every `HardGateName` `value` present; locked gloss strings
  present; no extra checkbox values.
- Existing guided-form value loop and Load example stay green.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
