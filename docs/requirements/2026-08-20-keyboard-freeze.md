---
title: "Ctrl/Cmd+Enter previews then freezes without inventing FOUND"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.1"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-protocol-preview.md
  - docs/requirements/2026-08-20-before-bed-stage.md
---

# Ctrl/Cmd+Enter previews then freezes without inventing FOUND

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning console keyboard shortcut for Preview then
Freeze. Not a new hard gate. Not inventing `FOUND`. Not unfreezing
`webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not changing CLI.

## 1. Why this cycle exists

PRD §4.1 is one-minute submit: state a hypothesis, preview the
protocol, freeze. Nielsen heuristic 7 (flexibility and efficiency of
use) says experts should not be forced through the mouse. The
packaged page has no keyboard path. GitHub / Slack / linear editors
use Ctrl/Cmd+Enter to send; that chord must not skip Preview, because
Freeze stays disabled until Preview succeeds.

Plain Enter in a field must not create a job. The form already has
`onsubmit="return false"`. This cycle must keep that lock.

## 2. Best-practice basis

1. **Recognition:** a visible `#keyboard-hint` names the chord. Do
   not hide it in a tooltip-only title.
2. **Preview still gates Freeze.** First Ctrl/Cmd+Enter calls the
   same `previewProtocol` path as the button. Second call, only if
   `#submit-job` is enabled, calls `submitJob`. A failed preview
   must not POST `/v1/jobs`.
3. **Do not steal typing.** Only Ctrl or Meta plus Enter. Prevent
   default so a focused textarea does not insert a newline.
4. **Do not invent FOUND.** The shortcut cannot override gates or
   skip dataset fail-closed.

## 3. In-scope requirements

### R1. Chord

A window `keydown` listener MUST:

- ignore unless `key` is `Enter` and (`ctrlKey` or `metaKey`);
- `preventDefault`;
- if `#submit-job` is not `disabled`, call `submitJob`;
- otherwise call `previewProtocol`.

It MUST NOT listen for unmodified Enter. It MUST NOT POST a job when
Freeze is disabled.

### R2. `#keyboard-hint`

Inside `#submit .actions`, after the three buttons, a
`#keyboard-hint` node MUST contain this text, verbatim:

`Ctrl/Cmd+Enter: Preview, then Freeze.`

MUST NOT contain `target found`. MUST NOT contain "override".

### R3. Docs

`docs/webui.md` first-release lead MAY mention Ctrl/Cmd+Enter.
Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC unchanged.

## 4. Out of scope

- Binding letter keys (p, s) that steal typing. Auto-preview on
  every keystroke. Auto-submit on first paint. Soak. \(N_{\mathrm{eff}}\).
- FakeWorker in morning e2e.

## 5. Acceptance

- Static: `keydown`, `ctrlKey`, `metaKey`, `previewProtocol` and
  `submitJob` in the handler; `#keyboard-hint` locked sentence;
  submit still starts `disabled`.
- E2E: Load example, Ctrl+Enter enables Freeze and creates no job;
  second Ctrl+Enter creates a job; legal outcomes only.
- Locks: no `target found`; no gate override; no FakeWorker in
  morning e2e.
