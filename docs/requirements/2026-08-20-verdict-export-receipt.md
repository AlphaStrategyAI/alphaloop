---
title: "Export receipt lives in the morning verdict, not below the report"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-console-export-receipt.md and found-handoff.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-found-handoff.md
  - docs/requirements/2026-08-20-console-export-receipt.md
  - docs/requirements/2026-08-20-job-keys.md
---

# Export receipt lives in the morning verdict, not below the report

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Placement of `#export-status` in the packaged morning
verdict cluster, and clearing it when the selected job changes.
Not a new hard gate. Not inventing `FOUND`. Not auto-export.
Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\).
Not changing CLI export stdout or `assert_exportable`.

## 1. Why this cycle exists

PRD §4.3 / §5.2: the morning console leads with the conclusion, then
the qualifying handoff. **Export .asb** already sits in `#handoff`
inside `#verdict`. The four-line FOUND receipt still renders in
`#export-status` below `#report` and the qualifying list.

A five-minute reader clicks Export next to `FOUND` and has to hunt
past the report for the receipt. Nielsen: recognition rather than
recall. Tufte: keep the claim next to the action.

`loadJobs` polls `showJob` every two seconds, so the receipt must
not be wiped on a same-job refresh. Switching jobs with `j`/`k` or a
click must not leave a prior job's `FOUND` receipt on a different
outcome.

## 2. Best-practice basis

1. **Same cluster as the click.** `#export-status` MUST sit inside
   `#verdict` immediately after `#handoff` and before `#job-status`.
2. **One node.** Do not duplicate `#export-status`. `#qualifying`
   below the report stays the full candidate list.
3. **Do not invent FOUND.** Clear `#export-status` when `showJob`
   selects a **different** `run_id`. Same-id poll MUST keep the
   receipt. Copy stays `format_export_handoff` via `export_handoff`.
4. **Do not claim alpha.** Receipt text unchanged. Help /
   `HOST_CONSTRAINT` unchanged.

## 3. In-scope requirements

### R1. Markup

Packaged `#detail` MUST contain exactly one `#export-status`.
DOM order:

`#handoff` < `#export-status` < `#job-status`

`#export-status` is a child of `#verdict`. Existing CSS
`white-space: pre-wrap` stays. No webfont `http`.

### R2. Clear on job change

At the start of `showJob(runId)`, if `currentRunId !== runId`, set
`#export-status` text to empty. Then assign `currentRunId`.
`exportCandidate` success still writes `export_handoff`.

### R3. Docs

`docs/webui.md` MAY note that the receipt sits in the verdict
cluster. Skill / Help / EXAMPLE_SPEC unchanged.

## 4. Out of scope

- Auto-export. Changing receipt copy. Soak. \(N_{\mathrm{eff}}\).
  FakeWorker in morning e2e. Unfreezing `webui/`. CLI stdout.

## 5. Acceptance

- Static: `#handoff` before `#export-status` before `#job-status`;
  script compares `currentRunId !== runId` and clears
  `#export-status`; no `http` webfont; no `override`.
- E2E: when outcome is `FOUND` and the human clicks Export,
  `#verdict #export-status` starts with `FOUND` and includes the
  no-alpha sentence and `.asb`.
- Locks: no `target found`; no invented `FOUND`; `gates.json` still
  not exportable.
