# CLI replay latest job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop replay` without a run id rewrites `report.md` for the latest job.

**Architecture:** `run_id` nargs=`?`. When omitted, `JobStore.list_jobs()[0].run_id` (offline). Empty → locked stderr + 2. Human omit prefixes `run_id:`.

**Tech Stack:** argparse, JobStore, pytest.

**Spec:** `docs/requirements/2026-08-20-replay-latest.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change verdict copy. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not require the daemon for replay.

---

### Task 1: Optional RUN_ID

**Files:**
- Modify: `src/alphaloop/cli/jobs.py`
- Modify: `docs/cli.md`, `README.md`, `docs/index.md`, `src/alphaloop/skills/overnight-lab/SKILL.md`, `mkdocs.yml`
- Test: `tests/runtime/test_cli_jobs.py`

- [ ] **Step 1: Failing tests**

Parser: `parse_args(["replay"]).run_id is None`.

Replay omit: two jobs with sealed `gates.json` on the newest, omit id, first line `run_id: {newest}`, then `FOUND`. No daemon.

Empty: no jobs, `alphaloop replay --data-dir` → 2, stderr `error: no overnight job yet\n`.

Explicit replay first line still `FOUND`.

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_cli_jobs.py::test_replay_without_run_id_uses_latest -v
```

- [ ] **Step 3: Implement**

`nargs="?"` on replay. Resolve `list_jobs()[0]` before the existing `run_replay` body.

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(cli): replay without a run id uses the latest job"
```
