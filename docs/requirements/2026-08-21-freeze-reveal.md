---
title: "Freeze reveals the selected morning job"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-21"
supersedes: "none — additive to 2026-08-20-preview-before-freeze.md / 2026-08-20-morning-lead.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-preview-before-freeze.md
  - docs/requirements/2026-08-20-morning-lead.md
---

# Freeze reveals the selected morning job

**Date:** 2026-08-21
**Status:** Approved for this implementation cycle
**Scope:** After a successful Freeze, the packaged console keeps the
selected morning job on screen. Wide layout: Morning stays visible
while Before bed scrolls. Not inventing `FOUND`. Not unfreezing
`webui/`. Not soak. Not \(N_{\mathrm{eff}}\).

## 1. Why this cycle exists

PRD §4.1: submission returns a `run_id` immediately. PRD §4.3: the
home page leads with that job's conclusion. Nielsen heuristic 1:
system status should be visible.

Preview-before-freeze put the protocol card above Freeze, so Before
bed is taller than a short viewport. Freeze is the commit control.
Clicking it (or Ctrl/Cmd+Enter) scrolls Freeze into view. Morning
sits in the other column (wide) or below Before bed (narrow). After
Freeze, `submitJob` already selects the new `run_id` and
`loadJobs` opens detail — but the selected card can remain off
screen. A one-minute user can freeze a protocol and never see the
overnight job they just queued.

The two-second job poll must not keep yanking the viewport.

## 2. Best-practice basis

1. **Immediate feedback.** A successful Freeze MUST bring the
   selected job card (`#job-list button[aria-current="true"]`) into
   the viewport. Fallback: `#morning`.
2. **Do not fight the reader.** `scrollIntoView` belongs in
   `submitJob` after a successful POST, not in `loadJobs`. Instant
   alignment (`block: "nearest"`), not smooth scrolling.
3. **Wide layout keeps Morning in the frame.** When `#console` is a
   two-column grid, `#morning` MUST stay sticky so scrolling to
   Freeze does not hide last night's (or the empty) morning pane.
4. **Do not claim alpha.** No new FOUND copy. Help /
   `HOST_CONSTRAINT` / EXAMPLE_SPEC stay locked.

## 3. In-scope requirements

### R1. Freeze reveals the selected card

After a successful `POST /v1/jobs` and `await loadJobs()`, packaged
`submitJob` MUST call `scrollIntoView({ block: "nearest", inline:
"nearest" })` on `#job-list button[aria-current="true"]`. If that
node is missing, scroll `#morning` instead.

A failed submit (non-OK response) MUST return before this scroll.
`loadJobs` (including the two-second poll) MUST NOT call
`scrollIntoView`.

### R2. Sticky Morning on the two-column grid

In the `@media (min-width: 56rem)` two-column layout, packaged
`#morning` MUST use `position: sticky` with a `top` offset and a
`max-height` that fits the viewport (`calc(100vh - …)`), plus
`overflow: auto` so a long detail pane scrolls inside Morning
instead of pushing Freeze off the opposite column.

The existing 960px `#console` grid stays. Do not change Help /
button chrome.

### R3. Docs

`docs/webui.md` MUST say Freeze reveals the selected morning job,
and that on a wide console Morning stays visible while Before bed
scrolls.

## 4. Out of scope

- Auto-submit. Restyling Load / Preview / Freeze. Expanding
  `#report` max-height. Soak. \(N_{\mathrm{eff}}\). Unfreezing
  `webui/`. Changing `HOST_CONSTRAINT`.

## 5. Acceptance

- Static: `scrollIntoView` appears in `submitJob` and not in
  `loadJobs`; `#morning { position: sticky }` exists under the
  56rem (or wider) grid.
- E2E short viewport (800×560): after example Freeze, the selected
  job card intersects the viewport.
- E2E wide short viewport (1280×560): with the YAML fold open and
  Freeze scrolled into view, `#morning` still intersects the
  viewport before submit.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
