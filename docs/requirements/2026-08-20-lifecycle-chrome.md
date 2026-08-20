---
title: "Cancel and Resume are designed overnight controls"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-lifecycle-actions.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-lifecycle-actions.md
  - docs/requirements/2026-08-20-handoff-export-button.md
  - docs/requirements/2026-08-20-next-step-button.md
  - docs/requirements/2026-08-20-overnight-liveness.md
  - docs/requirements/2026-08-20-failed-recovery.md
---

# Cancel and Resume are designed overnight controls

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning CSS for `#cancel-job` / `#resume-job`.
Not a new hard gate. Not inventing `FOUND`. Not changing hide/show.
Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\).
Not changing CLI cancel/resume stdout.

## 1. Why this cycle exists

PRD §5.2 / §5.3: Cancel and Resume are first-class overnight controls.
They already sit above `#report`. Verdict **Export .asb** uses FOUND
`--accent`. Verdict **Load into editor** uses NO_EVIDENCE `--warn`.
Cancel and Resume are still the generic `button` rule (`#1b2230`).

A researcher who sees a running pulse or a failed recovery still gets a
raw form button for the overnight control. Nielsen: consistency and
standards. Tufte: visual weight should match the cluster.

Hide/show stays: Cancel when queued or running; Resume when failed.
This cycle is paint, not a new gate.

## 2. Best-practice basis

1. **Same chrome family as Export/Load.** `#cancel-job` and
   `#resume-job` MUST set non-UA `background`, `border`,
   `border-radius`, `padding`, `font`, and `cursor`. Background is
   `--ink` (`#0b0f16`), matching Export/Load.
2. **Cancel is liveness, not FOUND.** `#cancel-job` MUST use `--focus`
   for border and text (same focus blue as the running pulse). MUST
   NOT use `--accent` / FOUND green.
3. **Resume is failed recovery, not FOUND.** `#resume-job` MUST use
   `--warn` for border and text (same as failed-job border). MUST NOT
   use `--accent` / FOUND green.
4. **Do not claim alpha.** No new copy. Help / `HOST_CONSTRAINT`
   unchanged. No `target found`.
5. **No webfont `http`.**

## 3. In-scope requirements

### R1. Shared chrome

Packaged `styles.css` MUST include `#cancel-job` and `#resume-job`
rules (or a grouped selector) that set non-UA `background`, `border`,
`border-radius`, `padding`, `font`, and `cursor`. Background MUST be
`var(--ink)`.

### R2. Status-token colors

`#cancel-job` MUST set `border-color` and `color` to `var(--focus)`.
That rule MUST NOT contain `var(--accent)`.

`#resume-job` MUST set `border-color` and `color` to `var(--warn)`.
That rule MUST NOT contain `var(--accent)`.

### R3. Docs

`docs/webui.md` MAY note Cancel uses focus-blue chrome and Resume uses
warn chrome, neither FOUND green. Skill / Help / EXAMPLE_SPEC
unchanged.

## 4. Out of scope

- Changing hide/show. Auto-resume. Soak. \(N_{\mathrm{eff}}\).
  FakeWorker in morning e2e. Unfreezing `webui/`. Restyling Export or
  Load (already shipped). Changing CLI cancel/resume.

## 5. Acceptance

- Static: `#cancel-job` / `#resume-job` chrome + color rules; cancel
  block has `--focus` not `--accent`; resume block has `--warn` not
  `--accent`.
- E2E: visible Cancel `color` is `rgb(126, 184, 255)`; visible Resume
  `color` is `rgb(255, 176, 32)`; wait until `getComputedStyle` matches
  (do not one-shot). Hide/show and cancel-before-seal stay
  `INCONCLUSIVE`.
- Locks: no invented `FOUND`. No FOUND green on these controls.
