---
title: "Failed overnight jobs show the worker error and recovery count"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.2 / §5.1 / §5.3"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-overnight-liveness.md
  - docs/requirements/2026-08-20-checkpoint-sigkill.md
---

# Failed overnight jobs show the worker error and recovery count

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning console rendering of existing
`morning_view.error` and `morning_view.recovery_attempts`. Not a new
hard gate. Not inventing `FOUND`. Not unfreezing `webui/`. Not soak.
Not \(N_{\mathrm{eff}}\). Not changing `format_status_verdict`.

## 1. Why this cycle exists

PRD §3.4 / §5.3: a crashed worker becomes a failed job with an
inconclusive research outcome; resume from checkpoint is the recovery
path. Running jobs now pulse and show `heartbeat_at`. Failed jobs
still look like sealed ones except for the word `failed` and a Resume
button. `morning_view` already carries `error` and
`recovery_attempts`. The page never prints them.

A researcher who left the host, found it asleep, and opened the
console cannot tell why the worker died or that recovery already
ran. Nielsen: visibility of system status. Do not hide the crash
behind a status token.

This is not a promise of alpha. A failed job with a heartbeat and an
error is still not `FOUND`.

## 2. Best-practice basis

1. **Show the stored failure, do not diagnose in the browser.** Print
   `job.error` and `job.recovery_attempts` as stored. Do not compute
   stale vs live. Do not invent a health badge.
2. **Failed is not FOUND.** Failed styling uses `--warn`, never
   `--accent`. No running pulse on failed (that cue is for live work).
3. **Resume stays the action.** `#resume-job` remains visible iff
   status is `failed`. This cycle does not auto-resume.
4. **Keep the CLI five-minute cluster.** Error and recovery stay off
   `format_status_verdict`. `--json` already has the fields.

## 3. In-scope requirements

### R1. `#job-error`

Packaged `#detail` MUST include `#job-error` after
`#worker-heartbeat`.

`showJob`: if `job.error` is a non-empty string, text is
`Worker error: {error}`; otherwise empty. MUST NOT contain
`target found`. MUST NOT invent `FOUND`.

### R2. `#recovery-attempts`

Packaged `#detail` MUST include `#recovery-attempts` after
`#job-error`.

`showJob`: if `Number(job.recovery_attempts) > 0`, text is
`Recovery attempts: {n}`; otherwise empty.

### R3. Job card recovery count

When `recovery_attempts > 0`, the job button MUST include a
`.job-recovery` span whose text is `recovery: {n}` (decimal).
Keep the existing `n_trials:` substring. Zero attempts: no
`.job-recovery` node.

### R4. Failed styling (packaged CSS only)

`#job-list button[data-status="failed"]` and
`#verdict[data-status="failed"]` MUST use a `--warn` border, not
`--accent`. They MUST NOT use `overnight-pulse`. No webfont `http`.
No gate override. Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC unchanged.

### R5. Docs

`docs/webui.md` first-release lead MAY mention that a failed job
shows the worker error, recovery count, and Resume.

## 4. Out of scope

- Auto-resume. Computing stale heartbeat in the page. SSE.
- Changing `format_status_verdict`. Soak. \(N_{\mathrm{eff}}\).
- FakeWorker in morning e2e.

## 5. Acceptance

- Static: `#job-error` after `#worker-heartbeat`; `#recovery-attempts`
  after `#job-error`; JS writes `Worker error:` and
  `Recovery attempts:`; `.job-recovery`; CSS failed selectors use
  warn and omit `overnight-pulse` on failed; no `http` in CSS.
- E2E: home includes `#job-error` and `#recovery-attempts`; after a
  job is open those nodes exist; `#resume-job` still shown for
  failed.
- Locks: no `target found`; no gate override; no FakeWorker in
  morning e2e.
