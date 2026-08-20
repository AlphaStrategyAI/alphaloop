---
title: "Before-bed stage groups the guided form and folds YAML"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to guided-spec-form.md / form-dataset.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-guided-spec-form.md
  - docs/requirements/2026-08-20-form-dataset.md
---

# Before-bed stage groups the guided form and folds YAML

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged `#before-bed` layout. Not unfreezing `webui/`. Not
changing EXAMPLE_SPEC. Not soak / \(N_{\mathrm{eff}}\) / MCP.

## 1. Why this cycle exists

PRD §4.1 is one-minute submit: state a hypothesis, choose a profile,
review the protocol, freeze. Nielsen: recognition rather than recall,
and aesthetic and minimalist design. The guided form now has many
controls, then a 16-row YAML editor. First paint looks like an admin
dump, not a lab desk. YAML is the canonical payload and must remain;
it must not be the visual lead.

## 2. Best-practice basis

1. **Stage the decision, hide the serialization.** The form is what a
   researcher recognizes. YAML is the frozen artifact.
2. **Group related controls.** Hypothesis, market, run, dataset, gates
   are separate questions. One undifferentiated grid forces scanning.
3. **Do not drop the canonical textarea.** Preview and Freeze still
   POST `#spec-yaml`. Folding is visibility, not a second protocol.

## 3. In-scope requirements

### R1. Form groups

`#hypothesis-form` MUST contain these fieldsets, in order, each with a
`.form-grid` of the listed controls (hard gates keep today's fieldset):

| id | legend |
| --- | --- |
| `#group-hypothesis` | Hypothesis |
| `#group-market` | Market |
| `#group-run` | Run |
| `#group-dataset` | Dataset |
| `#field-hard-gates` | Hard gates (unchanged) |

Control ids (`#field-statement` … `#field-dataset-file`) MUST stay.
Legends MUST NOT contain "override".

### R2. YAML fold

`#spec-yaml` MUST live inside `<details id="spec-yaml-fold">` whose
`<summary>` text is `Research spec (YAML)`. The fold is closed on first
paint (`open` absent). Load example, form sync, and Preview/Freeze
still read/write the textarea whether the fold is open or closed.

E2E helpers that `fill("#spec-yaml")` MUST open the fold first so
Playwright actionability holds.

### R3. Visual language

`.form-group` uses the same card surface as `#submit` (border, radius,
padding). No webfont `http` URLs. Help / `HOST_CONSTRAINT` unchanged.
No FakeWorker in morning e2e. No inventing `FOUND`.

## 4. Out of scope

- Removing YAML. Changing EXAMPLE_SPEC. Dataset fetch from the network.

## 5. Acceptance

- Static: group ids, fold wraps `#spec-yaml`, `.form-group` in CSS,
  `http` still absent from CSS.
- E2E: first open has `#spec-yaml-fold` not `[open]`; Load example
  still fills form and YAML; Preview/Freeze paths still work.
- Unit + e2e pytest as usual.

## 6. Loop exit

Remaining: human overnight soak; \(N_{\mathrm{eff}}\) must not shrink
DSR `N`; later MCP / cloud workers.
