---
title: "Torn trial-ledger JSONL must not block resume or mint FOUND"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §12"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-checkpoint-sigkill.md
---

# Torn trial-ledger JSONL must not block resume or mint FOUND

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Protocol ledger reader used on resume. Not soak. Not
\(N_{\mathrm{eff}}\). Not inventing `FOUND`. Not unfreezing `webui/`.

## 1. Why this cycle exists

PRD §12: recovery never treats partial artifacts as complete.
`SIGKILL` after a checkpoint is now tested, but `_append_ledger`
writes JSONL with a plain append. A kill **during** that write can
leave a truncated last line.

`alphaloop.runtime.artifacts_io`, `morning`, and `asb_export` already
skip `JSONDecodeError` lines. `alphaloop.protocol.loop._ledger_rows`
does `json.loads` on every non-empty line. Resume then crashes before
skipping completed ids. That is not durable overnight recovery.

## 2. Best-practice basis

1. **JSONL crash recovery:** skip unparseable lines (almost always
   the torn tail). Do not count them in unique `n_trials`.
2. **Do not treat garbage as a trial.** A truncated `"trial_id":`
   fragment is not a ledger id and must not inflate DSR `N`.
3. **Do not mint `FOUND` from a torn file.** Outcome still comes from
   sealed `GateEvidence`. Skipping a bad line is not a pass.

## 3. In-scope requirements

### R1. Protocol reader

`_ledger_rows` MUST skip lines that are empty, not JSON objects, or
raise `JSONDecodeError`. It MUST keep well-formed dict rows in file
order. Same behavior as `artifacts_io._ledger_rows`. Protocol MUST
NOT import `runtime`.

### R2. Resume

Given a ledger with one valid row plus a truncated trailing line,
`run_protocol` MUST return without `JSONDecodeError`. Unique parsed
`trial_id`s stay unique. `n_trials` passed into gates equals the
unique parsed id count (torn fragment excluded). The valid prior id
MUST NOT gain a second well-formed duplicate line.

### R3. Locks

`FOUND` only from complete `GateEvidence`. Do not shrink DSR `N`
below unique parsed ids. No FakeWorker. No `webui/` thaw.

## 4. Out of scope

- Rewriting the ledger file to drop the torn tail (skip-on-read is
  enough). Atomic JSONL rotation. Soak. \(N_{\mathrm{eff}}\).

## 5. Acceptance

- Unit: torn trailing line does not crash `run_protocol`; unique ids;
  `n_trials` ignores the fragment.
- Full unit + e2e pytest as usual.

## 6. Loop exit

Remaining: soak / 95% overnight (not CI); \(N_{\mathrm{eff}}\) must
not shrink DSR `N`. Later: MCP / cloud workers.
