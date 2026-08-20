---
title: "Freeze and submit uses designed accent chrome"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-preview-chrome.md / load-chrome.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-preview-chrome.md
  - docs/requirements/2026-08-20-load-chrome.md
  - docs/requirements/2026-08-20-keyboard-freeze.md
---

# Freeze and submit uses designed accent chrome

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning CSS for `#submit-job`. Not a new hard
gate. Not inventing `FOUND`. Not auto-submit. Not unfreezing
`webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not changing Preview,
Load, or click/disabled behavior.

## 1. Why this cycle exists

PRD §4.1: Load example → Preview protocol → Freeze. Preview and Load
use designed `--ink` chrome with `--focus` / `--fg`. **Freeze and
submit** still paints `#16352c` / `#2f6b55` hex instead of tokens.
Load-chrome named Freeze as already-shipped accent; the live rule is
ad-hoc fill. Nielsen: consistency. Tufte: the freeze control should
share the before-bed family, with FOUND `--accent` as its meaning.

Click behavior and `#submit-job:disabled` opacity stay. This cycle is
paint.

## 2. Best-practice basis

1. **Same chrome family as Preview.** `#submit-job` MUST set non-UA
   `background`, `border`, `border-radius`, `padding`, `font`, and
   `cursor`. Background is `--ink`. Size matches Preview
   (`0.55rem 0.8rem`, `0.45rem`).
2. **Freeze is FOUND accent, not Preview focus.** Border and text MUST
   use `var(--accent)` (`#3ee0a0` → `rgb(62, 224, 160)`). MUST NOT use
   `--focus` or `--warn` in that rule. MUST NOT keep `#16352c` or
   `#2f6b55`.
3. **Disabled stays honest.** `#submit-job:disabled` MAY keep opacity.
   MUST NOT invent `FOUND` copy.
4. **No webfont `http`.** Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC
   unchanged.

## 3. In-scope requirements

### R1. Designed chrome

Packaged `styles.css` MUST include `#submit-job` that sets non-UA
`background`, `border`, `border-radius`, `padding`, `font`, and
`cursor`. Background MUST be `var(--ink)`.

### R2. Accent color

That rule MUST set `color` and border to `var(--accent)`. It MUST NOT
contain `var(--focus)`, `var(--warn)`, `#16352c`, or `#2f6b55`.

### R3. Docs

`docs/webui.md` MUST note Freeze uses ink background and FOUND accent
chrome (not ad-hoc hex). Skill unchanged.

### R4. E2E

Playwright MUST `wait_for_function` until `#submit-job`
`getComputedStyle` color is `rgb(62, 224, 160)` and background is
`rgb(11, 15, 22)`. Do not one-shot.

## 4. Out of scope

- Auto-submit. Restyling Preview or Load. Soak. \(N_{\mathrm{eff}}\).
  FakeWorker in morning e2e. Unfreezing `webui/`. Changing freeze
  gating.

## 5. Acceptance

- Static: `#submit-job` block has `--ink` and `--accent`, not the old
  hex, not `--focus`.
- E2E: computed Freeze color/background match the tokens.
- Freeze stays disabled until a successful Preview.
