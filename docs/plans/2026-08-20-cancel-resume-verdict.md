# CLI cancel/resume verdict Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop cancel` and `alphaloop resume` print the five-minute verdict by default, with `--json` for agents.

**Architecture:** Reuse `format_status_verdict`. Add `--json` to cancel/resume. `_print_view` shared with `status RUN_ID`.

**Tech Stack:** Python 3.9+, argparse, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-cancel-resume-verdict.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- No FakeWorker in morning e2e. Do not unfreeze `webui/`.

---

### Task 1: Verdict + `--json`

**Files:**
- Modify: `src/alphaloop/cli/jobs.py`
- Modify: `docs/cli.md`
- Test: `tests/runtime/test_cli_jobs.py`
- Test: `tests/e2e/test_morning_console.py`

- [x] **Step 1: Failing tests**

```python
from alphaloop.contracts.status import JobStatus

def test_cancel_and_resume_parser_have_json_flag():
    parser = create_parser()
    assert parser.parse_args(["cancel", "j_x", "--json"]).json is True
    assert parser.parse_args(["resume", "j_x"]).json is False


def test_cancel_default_is_verdict_json_is_payload(tmp_path, capsys):
    # daemon + FakeWorker + store.create(_spec())
    rc = main(["cancel", job.run_id, "--data-dir", str(tmp_path)])
    human = capsys.readouterr()
    assert rc == 0
    assert human.out.splitlines()[0] == "INCONCLUSIVE"
    assert "Job status: cancelled" in human.out
    assert "This status does not claim alpha or future profitability." in human.out
    with pytest.raises(json.JSONDecodeError):
        json.loads(human.out)
    rc = main(["cancel", job.run_id, "--json", "--data-dir", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "cancelled"
    assert payload["research_outcome"] == "INCONCLUSIVE"


def test_resume_default_is_verdict_json_is_payload(tmp_path, capsys):
    job = store.create(_spec())
    store.update_status(job.run_id, JobStatus.FAILED, error="worker crashed")
    rc = main(["resume", job.run_id, "--data-dir", str(tmp_path)])
    human = capsys.readouterr()
    assert rc == 0
    assert human.out.splitlines()[0] == "NONE"
    assert "Job status: queued" in human.out
    rc = main(["resume", job.run_id, "--json", "--data-dir", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "queued"
```

E2E `test_cancel_before_seal_is_inconclusive`: `_cli(..., "cancel", "--json", run_id)` for payload; also `_cli(..., "cancel", run_id)` is already consumed — use `--json` for payload then human is N/A after cancel. Change to `--json` for json.loads. Add after payload: we only cancel once. Assert human by using `--json` for payload only, OR cancel with default and parse first line:

Better: cancel default (human), assert first line INCONCLUSIVE, then get payload via `status --json`.

```python
cancelled = _cli(..., "cancel", run_id)
assert cancelled.stdout.splitlines()[0] == "INCONCLUSIVE"
payload = json.loads(_cli(..., "status", "--json", run_id).stdout)
assert payload["status"] == "cancelled"
```

Resume e2e: `_cli(..., "resume", "--json", run_id)` keep json.loads.

- [x] **Step 2: FAIL**

- [x] **Step 3: Implement `--json` + `_print_view`**

- [x] **Step 4: Full unit + e2e**

- [x] **Step 5: Commit**
