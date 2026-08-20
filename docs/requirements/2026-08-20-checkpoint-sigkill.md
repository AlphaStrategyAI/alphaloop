---
title: "SIGKILL at a complete checkpoint must resume without duplicate trials or invented FOUND"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §12"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/plans/2026-08-19-overnight-lab-phase11-verification.md
---

# SIGKILL at a complete checkpoint must resume without duplicate trials or invented FOUND

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Process-level fault injection against the default protocol
worker. Not soak. Not \(N_{\mathrm{eff}}\). Not inventing `FOUND`.
Not unfreezing `webui/`. Not MCP.

## 1. Why this cycle exists

PRD §12 Resilience:

- Fault injection kills workers at each checkpoint boundary.
- Recovery never treats partial artifacts as complete.
- Incomplete evidence cannot produce `FOUND`.

Phase 11 already has an in-process `RuntimeError` inside `on_trial`
(`tests/runtime/test_checkpoint_resume.py`) and a morning e2e that
only checks `resume` returns `queued`/`running`. Neither proves the
**default `run_worker` process** can be `SIGKILL`'d after a complete
checkpoint and continue without duplicate `trial_id`s or a `FOUND`
minted from a checkpoint file alone.

That is the overnight-lab durability claim: host interruption is
expected; the ledger and gates stay honest.

## 2. Best-practice basis

1. **Kill the real entrypoint.** `python -m alphaloop.runtime.worker`
   is what `ProcessWorker` spawns. Injecting a Python exception in
   the same interpreter is not a checkpoint-boundary crash.
2. **Skip complete ids, re-run in-flight work.** Ledger append
   happens before `on_trial`. A kill between append and checkpoint
   may leave a `trial_id` that is not in `completed_trial_ids`.
   Resume MUST NOT append a second line for that id. Unique
   `trial_id` count is the DSR `n_trials` input.
3. **Checkpoint is not a gate.** `complete_from_artifacts` after a
   kill with no readable `gates.json` MUST be `INCONCLUSIVE`, never
   `FOUND`. After a clean resume, `FOUND` only if sealed evidence is
   complete and all required gates passed.

## 3. In-scope requirements

### R1. Process kill after first complete checkpoint

A shortened Job API run (fixture parquet, `hard_gates=("dsr",)`,
`time_budget_s` ≥ 30) starts `python -m alphaloop.runtime.worker`.
Once `load_latest_complete` returns a checkpoint whose payload
includes `completed_trial_ids`, the test sends `SIGKILL` if the
process is still alive.

If no complete checkpoint appears before the worker exits, the test
MAY skip (cannot inject at a boundary). It MUST NOT invent a
checkpoint file.

### R2. Mid-crash honesty

Immediately after the kill, if `evidence/gates.json` is missing or
unreadable, `JobStore.complete_from_artifacts` MUST NOT yield
`FOUND`.

### R3. Resume

A second `run_worker` on the same `run_id` MUST:

- exit 0;
- leave unique `trial_id`s in `trial-ledger.jsonl` (duplicates
  forbidden even if the in-flight id was already appended);
- keep every id that was in the killed checkpoint's
  `completed_trial_ids`;
- expose `morning_view.n_trials` equal to the unique ledger count;
- after `complete_from_artifacts`, allow `FOUND` only when
  `evidence.complete` and `evidence.all_passed` are both true.

No `target found` copy. No FakeWorker.

## 4. Out of scope

- Multi-host soak / 95% overnight (release checklist, not CI).
- \(N_{\mathrm{eff}}\) shrinking DSR `N`.
- Windows job-object kill. This cycle is POSIX `SIGKILL`.
- Changing checkpoint on-disk schema.

## 5. Acceptance

- Unit/integration: `tests/runtime/test_checkpoint_resume.py` covers
  R1–R3 against a real worker subprocess.
- Existing `test_second_start_skips_checkpointed_trial_ids` stays.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.

## 6. Loop exit

Remaining: soak / 95% overnight (not CI); \(N_{\mathrm{eff}}\) must
not shrink DSR `N`. Later: MCP / cloud workers.
