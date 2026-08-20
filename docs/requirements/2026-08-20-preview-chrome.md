---
title: "Preview protocol is a designed before-bed control"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-protocol-preview.md / keyboard-freeze.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-protocol-preview.md
  - docs/requirements/2026-08-20-keyboard-freeze.md
  - docs/requirements/2026-08-20-lifecycle-chrome.md
---

# Preview protocol is a designed before-bed control

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning CSS for `#preview-protocol`. Not a new
hard gate. Not inventing `FOUND`. Not auto-submit. Not unfreezing
`webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not changing CLI
preview stdout. Not restyling Freeze.

## 1. Why this cycle exists

PRD §4.1: review the protocol, then freeze. The packaged page already
gates Freeze on a successful Preview. Ctrl/Cmd+Enter is Preview, then
Freeze. **Freeze and submit** already uses designed accent chrome.
**Preview protocol** is still the generic `button` rule (`#1b2230`).

A one-minute submitter sees a raw form button for the step that
discloses `planned_n_trials` before an overnight job. Nielsen:
consistency and standards. Cancel already uses `--focus` for
liveness; Preview is the before-bed counterpart (look at the grid,
do not claim alpha).

Click behavior unchanged. This cycle is paint.

## 2. Best-practice basis

1. **Same chrome family as overnight controls.** `#preview-protocol`
   MUST set non-UA `background`, `border`, `border-radius`,
   `padding`, `font`, and `cursor`. Background is `--ink`.
2. **Preview is focus, not FOUND.** Border and text MUST use
   `--focus` (same as Cancel / running pulse). MUST NOT use
   `--accent` / FOUND green. Freeze keeps its existing accent rule.
3. **Match Freeze size.** Padding and radius MUST match the generic
   before-bed `button` (`0.55rem 0.8rem`, `0.45rem`), not the smaller
   verdict Export/Load chips.
4. **Do not claim alpha.** No new copy. Help / `HOST_CONSTRAINT`
   unchanged.
5. **No webfont `http`.**

## 3. In-scope requirements

### R1. Designed chrome

Packaged `styles.css` MUST include `#preview-protocol` that sets
non-UA `background`, `border`, `border-radius`, `padding`, `font`,
and `cursor`. Background MUST be `var(--ink)`.

### R2. Focus color

`#preview-protocol` MUST set `border-color` and `color` to
`var(--focus)`. That rule MUST NOT contain `var(--accent)`.

### R3. Docs

`docs/webui.md` MAY note Preview uses focus-blue chrome, not FOUND
green. Skill / Help / EXAMPLE_SPEC unchanged.

## 4. Out of scope

- Auto-submit. Restyling `#submit-job` or `#load-example`. Soak.
  \(N_{\mathrm{eff}}\). FakeWorker in morning e2e. Unfreezing
  `webui/`. Changing CLI preview.

## 5. Acceptance

- Static: `#preview-protocol` rule with `--ink` and `--focus`, not
  `--accent`.
- E2E: home page waits until `#preview-protocol`
  `getComputedStyle` `.color` is `rgb(126, 184, 255)` and
  `.backgroundColor` is `rgb(11, 15, 22)`. Freeze still starts
  disabled. Do not one-shot computed style.
- Locks: no invented `FOUND`. Preview does not use FOUND green.
