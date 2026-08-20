---
title: "Verdict Export .asb is a designed FOUND handoff control"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-found-handoff.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-found-handoff.md
  - docs/requirements/2026-08-20-verdict-export-receipt.md
  - docs/requirements/2026-08-19-five-minute-morning-review.md
---

# Verdict Export .asb is a designed FOUND handoff control

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning CSS for `#handoff button.export-asb`.
Not a new hard gate. Not inventing `FOUND`. Not auto-export.
Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\).
Not changing `assert_exportable`, CLI stdout, or Help copy.

## 1. Why this cycle exists

PRD §5.2: the console is the primary product surface. PRD §8.2:
export is a **human** AlphaStrategy handoff. The five-minute
**Export .asb** control already lives in `#handoff` inside
`#verdict`. Qualifying-list export buttons use designed chrome
(`#qualifying .export-asb`). The verdict button is still the
user-agent default.

A five-minute reader who just read `FOUND` sees a raw form button
next to the survivor id. Nielsen: consistency and standards; the
same action must look like the same control. Tufte: the visual
weight of the handoff should match its place in the cluster, not
disappear into browser chrome.

`#handoff` still renders only on `FOUND` with a `c_*` id. This
cycle is paint, not a new gate.

## 2. Best-practice basis

1. **Same chrome as the list button.** `#handoff .export-asb` MUST
   share background, radius, padding, and font with
   `#qualifying .export-asb`.
2. **FOUND token color, not a second green.** Inside
   `#verdict[data-outcome="FOUND"]`, the handoff button MUST use
   `--accent` for border and text so it reads as the FOUND handoff.
   MUST NOT use FOUND green on other outcomes (the node is empty
   there anyway).
3. **Do not claim alpha.** No new copy. Help / `HOST_CONSTRAINT`
   unchanged. No `target found`.
4. **No webfont `http`.**

## 3. In-scope requirements

### R1. Shared chrome

Packaged `styles.css` MUST include a `#handoff .export-asb` rule
(or a grouped selector with `#qualifying .export-asb`) that sets
non-UA `background`, `border`, `border-radius`, `padding`,
`font`, and `cursor`.

### R2. FOUND emphasis

`#verdict[data-outcome="FOUND"] #handoff .export-asb` MUST set
`border-color` and `color` to `var(--accent)`.

### R3. Docs

`docs/webui.md` MAY mention the verdict Export control. Skill /
Help / EXAMPLE_SPEC unchanged.

## 4. Out of scope

- Auto-export. Restyling `#next-step .load-queued`. Soak.
  \(N_{\mathrm{eff}}\). FakeWorker in morning e2e. Unfreezing
  `webui/`. Changing receipt copy.

## 5. Acceptance

- Static: `#handoff .export-asb` and
  `#verdict[data-outcome="FOUND"] #handoff .export-asb` in CSS;
  `var(--accent)` in that FOUND rule; `http` not in CSS; no
  `override` in the script.
- E2E: when the page outcome is `FOUND`, the verdict Export button
  computed `border-color` and `color` use the accent green
  `rgb(62, 224, 160)`.
- Locks: no invented `FOUND`; no Python in `.asb`.
