---
title: "Cancel and Resume sit above the report, not below it"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-failed-recovery.md / overnight-liveness.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-failed-recovery.md
  - docs/requirements/2026-08-20-overnight-liveness.md
  - docs/requirements/2026-08-20-verdict-export-receipt.md
---

# Cancel and Resume sit above the report, not below it

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Placement of packaged `#cancel-job` / `#resume-job`.
Not a new hard gate. Not inventing `FOUND`. Not changing hide/show
rules. Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\).
Not changing CLI cancel/resume stdout.

## 1. Why this cycle exists

PRD §4.2 / §5.3: closing the browser does not stop a job; a crashed
worker becomes a failed job and resume from checkpoint is the
recovery path. The five-minute cluster now leads with outcome,
liveness, worker error, and recovery count. **Cancel** and **Resume**
still sit in `.actions` *below* `#report`.

A researcher who sees `running` or `failed` has to hunt past the
report for the overnight control. Nielsen: recognition rather than
recall. Same placement bug as the export receipt before it moved
into the verdict.

Hide/show stays: Cancel when queued or running; Resume when failed.
This cycle is placement, not a new gate.

## 2. Best-practice basis

1. **Controls next to status.** After `#recovery-attempts`, before
   `#hypothesis-statement` and `#report`.
2. **Do not invent FOUND.** Moving the buttons must not change
   `research_outcome` or un-hide them on sealed completed jobs.
3. **One `.actions` node.** Do not duplicate Cancel/Resume.
4. **Help / `HOST_CONSTRAINT` unchanged.**

## 3. In-scope requirements

### R1. Markup

Packaged `#detail` MUST contain exactly one `#cancel-job` and one
`#resume-job`, still inside `p.actions`. DOM order:

`#recovery-attempts` < `#cancel-job` < `#report` < `#qualifying`

### R2. Behavior

`showJob` hide/show rules unchanged:

- `#cancel-job` hidden unless `status` is `queued` or `running`
- `#resume-job` hidden unless `status` is `failed`

Click handlers unchanged.

### R3. Docs

`docs/webui.md` MAY note that Cancel/Resume sit above the report.
Skill / Help / EXAMPLE_SPEC unchanged.

## 4. Out of scope

- Auto-resume. Changing CLI cancel/resume. Soak. \(N_{\mathrm{eff}}\).
  FakeWorker in morning e2e. Unfreezing `webui/`. Restyling the
  generic `button` rule.

## 5. Acceptance

- Static: recovery-attempts < cancel-job < report < qualifying;
  resume-job in the same `.actions` node as cancel-job.
- E2E: `test_cancel_from_console_before_seal_is_inconclusive` still
  clicks `#cancel-job` and gets `INCONCLUSIVE`.
- Locks: no `target found`; no invented `FOUND`.
