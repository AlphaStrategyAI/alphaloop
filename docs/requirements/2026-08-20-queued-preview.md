---
title: "Preview queued follow-up without auto-submitting"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.3 / §6.1"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-queued-followup.md
  - docs/requirements/2026-08-20-morning-report.md
---

# Preview queued follow-up without auto-submitting

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** After "Load into editor", automatically preview the loaded
YAML so Freeze and submit can proceed with one human click. Not
auto-submit. Not inventing `FOUND`. Not running the follow-up in the
same overnight job.

## 1. Why this cycle exists

PRD §4.3 queues a future economic hypothesis for a human. The queued
cycle already loads the counterpart into the guided form. Preview is
still a second click the user must remember. Nielsen: recognition
rather than recall. One-minute iterate means: load the named
follow-up, see the frozen grid, then **explicitly** freeze.

Auto-submit would violate PRD §6.1 (a new `signal_mechanism` is a new
economic hypothesis; a human must freeze it). Auto-preview is the
protocol review step, not the freeze.

## 2. Best-practice basis

1. **Human freeze:** Submit stays the only mutation that creates a
   job. Load + preview MUST NOT POST `/v1/jobs` except `/preview`.
2. **Same preview gate:** `previewedYaml` and disabled Submit until
   preview succeeds, identical to the manual Preview protocol button.
3. **Do not invent `FOUND`.** Help / `HOST_CONSTRAINT` unchanged.

## 3. In-scope requirements

### R1. Auto-preview after load

Clicking `#queued button.load-queued` MUST fill the guided form as
today, reuse the selected job's `seed`, `time_budget_s`,
`cost_budget_usd`, and `dataset` when those form fields are empty
(so a morning page reload can still freeze), then call the existing
preview endpoint. On success, Freeze and submit becomes enabled. On
preview failure, Submit stays disabled and `#preflight-errors` shows
the errors.

### R2. No auto-submit

The click MUST NOT create a new job. Job list count stays unchanged
until the human clicks Freeze and submit.

### R3. Locks

`HOST_CONSTRAINT` unchanged. Example YAML unchanged. No
`FakeWorker` in morning e2e. No gate override.

## 4. Out of scope

- Textbook `S=16`. Soak. \(N_{\mathrm{eff}}\). MCP / cloud workers.
- Auto-running the counterpart overnight. Unfreezing `webui/`.

## 5. Acceptance

- Packaged script: load-queued path calls preview (`/v1/jobs/preview`).
- E2E: after Load into editor, Submit becomes enabled; still one job;
  no invented `FOUND`.
  `python3 -m pytest` unit + e2e as usual.

## 6. Loop exit

Remaining validation: textbook `S=16` CPCV, soak / 95% overnight
(not CI), correlation-adjusted \(N_{\mathrm{eff}}\). Later: MCP /
cloud workers.
