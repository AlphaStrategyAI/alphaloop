---
title: "Load example is a designed before-bed control"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-empty-morning.md / preview-chrome.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-empty-morning.md
  - docs/requirements/2026-08-20-preview-chrome.md
  - docs/requirements/2026-08-20-morning-console-ui.md
---

# Load example is a designed before-bed control

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning CSS for `#load-example`. Not a new hard
gate. Not inventing `FOUND`. Not auto-submit. Not unfreezing
`webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not changing example
YAML. Not restyling Preview or Freeze.

## 1. Why this cycle exists

PRD §4.1 / empty-morning: the one-minute path is **Load example →
Preview protocol → Freeze**. Preview now uses `--focus`. Freeze uses
`--accent`. **Load example** is still the generic `button` rule
(`#1b2230`).

A first-run researcher sees a raw form button for the first named
action in `#empty-morning`. Nielsen: consistency and standards.
Tufte: visual weight should match the cluster.

Click behavior and `EXAMPLE_SPEC` unchanged. This cycle is paint.

## 2. Best-practice basis

1. **Same chrome family as Preview/Freeze.** `#load-example` MUST set
   non-UA `background`, `border`, `border-radius`, `padding`,
   `font`, and `cursor`. Background is `--ink`. Size matches Freeze
   (`0.55rem 0.8rem`, `0.45rem`).
2. **Load is secondary, not a token.** Border and text MUST use
   `--fg` / `--line`. MUST NOT use `--accent` (FOUND / Freeze),
   `--warn` (NO_EVIDENCE / Resume), or `--focus` (Preview / Cancel).
3. **Do not claim alpha.** No new copy. Help / `HOST_CONSTRAINT` /
   EXAMPLE_SPEC unchanged.
4. **No webfont `http`.**

## 3. In-scope requirements

### R1. Designed chrome

Packaged `styles.css` MUST include `#load-example` that sets non-UA
`background`, `border`, `border-radius`, `padding`, `font`, and
`cursor`. Background MUST be `var(--ink)`.

### R2. Secondary color

`#load-example` MUST set `color` to `var(--fg)` and `border-color`
to `var(--line)`. That rule MUST NOT contain `var(--accent)`,
`var(--warn)`, or `var(--focus)`.

### R3. Docs

`docs/webui.md` MAY note Load example uses designed secondary chrome,
not FOUND green. Skill / Help / EXAMPLE_SPEC unchanged.

## 4. Out of scope

- Auto-submit. Changing example YAML. Soak. \(N_{\mathrm{eff}}\).
  FakeWorker in morning e2e. Unfreezing `webui/`. Restyling Preview
  or Freeze (already shipped).

## 5. Acceptance

- Static: `#load-example {` block has `--ink`, `--fg`, `--line`; not
  `--accent` / `--warn` / `--focus`.
- E2E: home page waits until `#load-example` `getComputedStyle`
  `.backgroundColor` is `rgb(11, 15, 22)` and `.color` is
  `rgb(243, 239, 230)`. Do not one-shot. Load still fills the
  example spec without creating a job.
- Locks: no invented `FOUND`.
