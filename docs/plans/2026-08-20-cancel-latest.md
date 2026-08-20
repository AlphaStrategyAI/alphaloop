# CLI cancel/resume latest job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop cancel` and `alphaloop resume` without a run id act on the latest job.

**Architecture:** `run_id` nargs=`?`. Shared resolve from `list_jobs()[0]`. Empty → locked stderr + 2. Omit path prefixes `run_id:` on human stdout.

**Tech Stack:** argparse, JobClient, pytest.

**Spec:** `docs/requirements/2026-08-20-cancel-latest.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change verdict copy. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not change `replay`.

---

### Task 1: Optional RUN_ID

**Files:**
- Modify: `src/alphaloop/cli/jobs.py`
- Modify: `docs/cli.md`, `README.md`, `src/alphaloop/skills/overnight-lab/SKILL.md`, `mkdocs.yml`
- Test: `tests/runtime/test_cli_jobs.py`

- [x] **Step 1: Failing tests**

Parser: `parse_args(["cancel"]).run_id is None`.

Cancel omit: two jobs, omit id, first line `run_id: {newest}`, then `INCONCLUSIVE`.

Empty: daemon up, no jobs, `alphaloop cancel --data-dir` → 2, stderr `error: no overnight job yet\n`.

Resume omit: failed job, omit id, `Job status: queued`.

Explicit cancel first line still `INCONCLUSIVE`.

- [x] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_cli_jobs.py::test_cancel_without_run_id_uses_latest -v
```

- [x] **Step 3: Implement**

`nargs="?"` on cancel/resume. Resolve latest before `_run_action`.

- [x] **Step 4: Tests pass**

- [x] **Step 5: Commit**

```bash
git commit -m "feat(cli): cancel and resume without a run id use the latest job"
```
