---
title: "Verdict Load into editor is a designed next-run control"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-next-run-cue.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-next-run-cue.md
  - docs/requirements/2026-08-20-handoff-export-button.md
---

# Verdict Load into editor is a designed next-run control

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning CSS for `#next-step button.load-queued`.
Not a new protocol proposer. Not auto-submit. Not inventing `FOUND`.
Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\).
Not changing Help / `HOST_CONSTRAINT`.

## 1. Why this cycle exists

PRD §4.3 / §6.1: after `NO_EVIDENCE`, the next economic hypothesis is
queued for a human. The five-minute **Load into editor** control
already lives in `#next-step` inside `#verdict`. The queued list
buttons use designed chrome (`#queued .load-queued`). The verdict
Export control now uses designed chrome. The next-run button is still
the user-agent default.

A five-minute reader who just read `NO_EVIDENCE` sees a raw form
button next to `Next run:`. Nielsen: consistency and standards.
Tufte: visual weight should match the cluster, not disappear into
browser chrome.

Load still fills the editor and requires Preview then Freeze. This
cycle is paint, not auto-run.

## 2. Best-practice basis

1. **Same chrome as the list button.** `#next-step .load-queued`
   MUST share background, radius, padding, and font with
   `#queued .load-queued`.
2. **NO_EVIDENCE token color, not FOUND green.** Inside
   `#verdict[data-outcome="NO_EVIDENCE"]`, the next-step button MUST
   use `--warn` for border and text. MUST NOT use `--accent` /
   FOUND green on this control.
3. **Do not auto-submit.** Click behavior unchanged.
4. **No webfont `http`.**

## 3. In-scope requirements

### R1. Shared chrome

Packaged `styles.css` MUST include `#next-step .load-queued` (or a
grouped selector with `#queued .load-queued`) that sets non-UA
`background`, `border`, `border-radius`, `padding`, `font`, and
`cursor`.

### R2. NO_EVIDENCE emphasis

`#verdict[data-outcome="NO_EVIDENCE"] #next-step .load-queued` MUST
set `border-color` and `color` to `var(--warn)`. That rule MUST NOT
contain `var(--accent)`.

### R3. Docs

`docs/webui.md` MAY mention the verdict Load control. Skill / Help /
EXAMPLE_SPEC unchanged.

## 4. Out of scope

- Auto-submit after Load. Changing queued hypothesis copy. Soak.
  \(N_{\mathrm{eff}}\). FakeWorker in morning e2e. Unfreezing
  `webui/`. Restyling Export (already shipped).

## 5. Acceptance

- Static: `#next-step .load-queued` and the NO_EVIDENCE-scoped rule
  in CSS; that rule uses `--warn` not `--accent`; `http` not in CSS.
- E2E: `test_load_queued_fills_editor_without_submitting` — the
  verdict Load button computed background is `--ink`
  `rgb(11, 15, 22)`; when `#verdict[data-outcome="NO_EVIDENCE"]`,
  border and text are `--warn` `rgb(255, 176, 32)`.
- Locks: no invented `FOUND`; Load does not create a job.
