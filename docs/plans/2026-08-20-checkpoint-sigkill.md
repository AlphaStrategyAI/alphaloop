# Checkpoint SIGKILL resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove a real worker process killed after a complete checkpoint resumes without duplicate ledger ids or a `FOUND` minted from incomplete evidence.

**Architecture:** Spawn `python -m alphaloop.runtime.worker`, wait for `load_latest_complete`, `SIGKILL`, assert mid-crash honesty, `run_worker` again, assert unique ids and sealed-FOUND lock. Production changes only if the test finds a real bug.

**Tech Stack:** Python 3.9+, pytest, POSIX SIGKILL, existing JobStore + `run_worker`.

**Spec:** `docs/requirements/2026-08-20-checkpoint-sigkill.md`

## Global Constraints

- Do not invent `FOUND`. Do not shrink DSR `N`. No FakeWorker in this test.
- `alphaloop.protocol` must not import `live` / `webui` / `runtime`.

---

### Task 1: Process-level SIGKILL resume test

**Files:**
- Modify: `tests/runtime/test_checkpoint_resume.py`
- Modify production only if the new test fails for a real recovery bug

- [ ] **Step 1: Write the failing or characterizing test**

Add to `tests/runtime/test_checkpoint_resume.py` a test that:

1. Writes a 260-bar AAPL/MSFT/SPY parquet under `datasets/ds_kill/`.
2. `JobStore.create` a spec with `hard_gates=("dsr",)`, matching `DatasetRef`.
3. `subprocess.Popen([sys.executable, "-m", "alphaloop.runtime.worker", "--run-id", run_id, "--data-dir", str(tmp_path)])`.
4. Polls `load_latest_complete` up to 60s; skip if none before exit.
5. `SIGKILL` if still alive; `wait`.
6. If `gates.json` missing: `complete_from_artifacts` is not `FOUND`.
7. Records ledger ids and checkpoint `completed_trial_ids`.
8. `assert run_worker(run_id, tmp_path) == 0`.
9. Unique ledger ids; checkpoint ids still present; `morning_view.n_trials` equals unique count; `FOUND` only with complete all-passed evidence.

- [ ] **Step 2: Run it**

Run: `python3 -m pytest tests/runtime/test_checkpoint_resume.py -v`

Expected: FAIL on a recovery bug, or PASS if Phase 9 already honors skip + unique ledger. Do not skip-pass by writing a fake checkpoint.

- [ ] **Step 3: Fix production only if needed**

Likely files: `src/alphaloop/runtime/worker.py` (`completed_trial_ids` from checkpoint), `src/alphaloop/protocol/loop.py` (do not re-append existing `trial_id`).

- [ ] **Step 4: Re-run unit + e2e**

```bash
python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration
python3 -m pytest tests/e2e -m e2e
```

- [ ] **Step 5: Commit**
