---
title: "Overnight liveness: running pulse and honest worker heartbeat"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.2 / §5.1 / §5.2"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-search-progress.md
  - docs/requirements/2026-08-20-morning-console-ui.md
---

# Overnight liveness: running pulse and honest worker heartbeat

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning console running/queued visual state, plus
`heartbeat_at` on `morning_view`. Not a new hard gate. Not inventing
`FOUND`. Not unfreezing `webui/`. Not soak execution. Not
\(N_{\mathrm{eff}}\). Not changing the CLI five-minute cluster.

## 1. Why this cycle exists

The product goal names a visually distinct, intuitively interactive
overnight lab. PRD §4.2: a local supervisor keeps the job alive
independently of the browser. PRD §5.1: the control plane tracks
worker heartbeats. Nielsen **visibility of system status**: running
vs sealed must be visible without opening YAML.

Job cards already set `data-status` and `data-outcome`. CSS only
styles outcome. A running overnight job looks the same as a sealed
one except for a status word. `morning_view` exposes `status` but
not `heartbeat_at`, so the page cannot show the timestamp the
supervisor already stores. Search progress shows grid walk; it does
not show that a worker is still beating.

This is not progress toward alpha. A pulse and a timestamp must not
imply `FOUND`.

## 2. Best-practice basis

1. **NN/g heuristic 1:** queued / running / sealed stay distinct.
   Running uses a motion cue; sealed uses outcome color.
2. **Do not use FOUND green for liveness.** Running pulse uses the
   existing `--focus` blue. Outcome colors stay for
   `FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE`.
3. **Honor `prefers-reduced-motion`.** Disable the pulse when the
   user asks for reduced motion. Keep `data-status` for recognition.
4. **Honest timestamp, no health theater.** Show the sealed
   `heartbeat_at` string. Do not compute "alive" / "stale" in the
   page (that would invent a second supervisor). Empty when null.
5. **Keep the five-minute CLI cluster.** `format_status_verdict`
   does not gain a heartbeat line.

## 3. In-scope requirements

### R1. `heartbeat_at` on `morning_view`

`morning_view` MUST include `heartbeat_at`: the job record's
`heartbeat_at` (`str | None`). It MUST NOT invent a timestamp. Existing
keys stay.

### R2. `#worker-heartbeat`

Packaged `#detail` MUST include `#worker-heartbeat` after
`#job-status`.

`showJob`:

- if `job.heartbeat_at` is a non-empty string, text is
  `Worker heartbeat: {heartbeat_at}` (verbatim prefix);
- otherwise text is empty.

The node MUST NOT claim alpha. It MUST NOT contain `target found`.

### R3. Running pulse (packaged CSS only)

`#verdict` MUST set `data-status` to `job.status` (same tokens as
the job button).

`#job-list button[data-status="running"]` and
`#verdict[data-status="running"]` MUST use a named `@keyframes`
animation (`overnight-pulse`) whose visible cue uses `--focus`, not
`--accent` (FOUND green).

`@media (prefers-reduced-motion: reduce)` MUST set
`animation: none` on those running selectors.

Queued / failed / cancelled MUST NOT use the FOUND green pulse.
No webfont `http` URLs. No Node. No gate override.

### R4. Docs

`docs/webui.md` first-release lead MAY mention that a running job
pulses and shows the worker heartbeat timestamp. Help /
`HOST_CONSTRAINT` / EXAMPLE_SPEC unchanged.

## 4. Out of scope

- Computing stale-heartbeat in the browser. SSE. Unfreezing `webui/`.
- Changing `format_status_verdict`. Soak execution. \(N_{\mathrm{eff}}\).
- FakeWorker in morning e2e.

## 5. Acceptance

- Unit: `morning_view` after `set_heartbeat` returns that `at`;
  create-only job has `heartbeat_at is None`.
- Static: `#worker-heartbeat` after `#job-status`; JS writes
  `Worker heartbeat:`; CSS has `overnight-pulse` and reduced-motion
  `animation: none`; no `http` in CSS.
- E2E: home has `#worker-heartbeat`; after a job is open, `#verdict`
  has `data-status`; list buttons keep `data-status`.
- Locks: no `target found`; no gate override; no FakeWorker in
  morning e2e.
