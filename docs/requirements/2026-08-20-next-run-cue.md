---
title: "Morning verdict stages the queued next run"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.3 / §6.1"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-primary-evidence.md
  - docs/requirements/2026-08-20-queued-followup.md
---

# Morning verdict stages the queued next run

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning `#verdict` cue for an already-queued
follow-up hypothesis. Not a new protocol proposer. Not auto-submit.
Not inventing `FOUND`. Not unfreezing `webui/`. Not soak.

## 1. Why this cycle exists

PRD §4.3: after the conclusion, the morning page presents
evidence-backed suggestions for a **future** hypothesis. PRD §6.1:
a new `signal_mechanism` is queued for a human; it is never executed
in the same overnight run.

Primary evidence and stop reason now sit in `#verdict`. The queued
counterpart after `NO_EVIDENCE` still lives under a heading at the
bottom of the detail pane. A five-minute reader who just learned
`dsr failed` still has to hunt for what to freeze next. Nielsen:
recognition rather than recall. The iterate loop is not intuitive if
the next constrained experiment is off-screen.

## 2. Best-practice basis

1. **Same cluster as the three five-minute tokens.** Conclusion,
   primary evidence, stop reason, then the human next action.
2. **Do not auto-run.** Load still fills the editor and requires
   Preview → Freeze. Changing `signal_mechanism` remains an economic
   revision.
3. **Do not invent a follow-up.** `#next-step` renders only
   `queued_hypotheses[0]` when that list is non-empty. Empty queue →
   empty node. No synthetic RSI suggestion on `FOUND` / `NONE`.
4. **Do not claim alpha.** Reuse the queued `statement` (already
   required to say it is not a claim of alpha). Prefix `Next run: `.

## 3. In-scope requirements

### R1. Markup

Packaged detail MUST include `#next-step` inside `#verdict` after
`#stop-reason` and before `#job-status`. Existing `#queued` list
stays the full record.

### R2. Render

`fillNextStep(job)`:

- If `job.queued_hypotheses` is missing or empty, `#next-step` has
  no children.
- Otherwise the first item's `statement` is shown as
  `Next run: {statement}` plus `button.load-queued` labelled
  `Load into editor` that calls the existing `loadQueuedHypothesis`
  (preview, no POST `/v1/jobs`).

`#outcome` text remains the research-outcome token.

### R3. Locks

`HOST_CONSTRAINT` unchanged. Help sentences unchanged. Example YAML
unchanged. No `FakeWorker` in morning e2e. No gate override.

## 4. Out of scope

- Writing a new follow-up when `recommendations.json` is empty
  (protocol already queues on `NO_EVIDENCE`).
- Soak. \(N_{\mathrm{eff}}\). MCP / cloud workers. Unfreezing `webui/`.

## 5. Acceptance

- Packaged HTML: `#stop-reason` < `#next-step` < `#job-status`.
- Packaged JS: `fillNextStep` and `Next run:`.
- E2E: after writing a queued row, `#verdict #next-step button.load-queued`
  fills `rsi` and does not create a second job.
- Unit + e2e pytest as usual.

## 6. Loop exit

Remaining first-release items: soak / 95% overnight (not CI);
correlation-adjusted \(N_{\mathrm{eff}}\) must not shrink DSR `N`.
Later: MCP / cloud workers.
