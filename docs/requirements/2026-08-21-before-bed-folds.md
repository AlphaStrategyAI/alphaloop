---
title: "Before bed folds Run, Dataset, and Hard gates"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-21"
supersedes: "none — additive to 2026-08-20-before-bed-stage.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-before-bed-stage.md
  - docs/requirements/2026-08-20-guided-spec-form.md
---

# Before bed folds Run, Dataset, and Hard gates

**Date:** 2026-08-21
**Status:** Approved for this implementation cycle
**Scope:** Packaged Before bed first paint. Hypothesis and Market stay
open. Run, Dataset, and Hard gates start folded, like YAML. Not
removing controls. Not inventing `FOUND`. Not unfreezing `webui/`.
Not soak. Not \(N_{\mathrm{eff}}\).

## 1. Why this cycle exists

PRD §4.1 one-minute submit: **state a hypothesis and choose a market
profile**, then review and freeze. Nielsen: aesthetic and minimalist
design; recognition rather than recall.

YAML is already in `#spec-yaml-fold`. Hypothesis, Market, Run,
Dataset, and Hard gates still occupy the full first paint. A
researcher who wants Load example → Preview → Freeze has to scroll
past seed, sha256, and six gate checkboxes. Bailey / López de Prado
disclosure of **N**, seed, and gates belongs on the protocol preview
card (already above Freeze), not as a wall of form controls before
the hypothesis.

Control ids stay. Load example, form sync, Preview, and Freeze still
read hidden fields. Preview remains the freeze-time disclosure.

## 2. Best-practice basis

1. **Progressive disclosure.** First paint shows Hypothesis and
   Market. Run, Dataset, and Hard gates are `<details>` closed on
   first paint, same pattern as YAML.
2. **Do not drop canonical controls.** Fieldset ids and input ids
   stay. Folding is visibility, not a second protocol.
3. **Do not claim alpha.** No new FOUND copy. Help /
   `HOST_CONSTRAINT` / EXAMPLE_SPEC stay locked.

## 3. In-scope requirements

### R1. Folds

Packaged `#hypothesis-form` MUST wrap, in order, after
`#group-market`:

| details id | summary | inner fieldset |
| --- | --- | --- |
| `#fold-run` | `Run` | `#group-run` |
| `#fold-dataset` | `Dataset` | `#group-dataset` |
| `#fold-gates` | `Hard gates` | `#field-hard-gates` |

Each fold is closed on first paint (`open` absent). Hypothesis and
Market MUST remain open fieldsets (not inside these folds).
`#spec-yaml-fold` stays after the form.

`html.find('id="group-market"') < html.find('id="fold-run"') <
html.find('id="group-run"')` and the same pattern for dataset and
gates.

### R2. First-paint geometry

On first paint Playwright MUST find `#group-hypothesis` and
`#group-market` visible, and `#group-run`, `#group-dataset`, and
`#field-hard-gates` not visible. The three fold summaries stay
visible. Opening `#fold-dataset` MUST make `#field-dataset-file`
actionable.

### R3. Docs

`docs/webui.md` MUST say Run, Dataset, and Hard gates start folded
so Hypothesis and Market lead the one-minute path.

## 4. Out of scope

- Removing YAML or fieldsets. Changing EXAMPLE_SPEC. Auto-open on
  Load example. Soak. \(N_{\mathrm{eff}}\). Unfreezing `webui/`.
  Restyling Load / Preview / Freeze.

## 5. Acceptance

- Static: three closed `<details>` wraps; group ids unchanged.
- E2E first paint: Hypothesis/Market visible; Run/Dataset/Gates
  hidden until the fold is opened.
- Existing dataset picker / empty-dataset e2e open `#fold-dataset`
  before fill / `set_input_files`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
