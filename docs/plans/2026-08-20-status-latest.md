# CLI status latest job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop status` with no run id leads with the latest job's five-minute verdict, or the locked empty cue.

**Architecture:** `run_id` is `nargs="?"`. Omit → `JobClient.list_jobs()`; use `jobs[0]` or `EMPTY_STATUS_CUE`. Explicit id path unchanged.

**Tech Stack:** Python 3.9+, argparse, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-status-latest.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. No FakeWorker in morning e2e.
- `status RUN_ID` first line stays the outcome token.

---

### Task 1: Optional run id + latest / empty

**Files:**
- Modify: `src/alphaloop/runtime/morning.py` (`EMPTY_STATUS_CUE`)
- Modify: `src/alphaloop/cli/jobs.py`
- Modify: `docs/cli.md`, `README.md`, `docs/index.md`
- Modify: `src/alphaloop/skills/overnight-lab/SKILL.md`
- Test: `tests/runtime/test_cli_jobs.py`
- Test: `tests/skills/test_overnight_lab_skill.py`
- Test: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: `JobClient.list_jobs() -> {"jobs": [morning_view, ...]}`
- Produces: `EMPTY_STATUS_CUE: str` (locked, trailing newline)

- [x] **Step 1: Write the failing tests**

In `tests/runtime/test_cli_jobs.py`:

```python
from alphaloop.runtime.morning import EMPTY_STATUS_CUE, STATUS_NO_ALPHA

def test_status_parser_run_id_optional():
    parser = create_parser()
    args = parser.parse_args(["status", "--json"])
    assert args.run_id is None
    assert args.json is True
    assert parser.parse_args(["status", "j_x"]).run_id == "j_x"


def test_status_without_run_id_leads_with_latest_or_empty(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    try:
        rc = main(["status", "--data-dir", str(tmp_path)])
        empty = capsys.readouterr()
        assert rc == 0
        assert empty.out == EMPTY_STATUS_CUE
        assert "target found" not in empty.out.lower()
        assert empty.out.splitlines()[-1] == STATUS_NO_ALPHA

        rc = main(["status", "--json", "--data-dir", str(tmp_path)])
        empty_json = capsys.readouterr()
        assert rc == 0
        assert json.loads(empty_json.out) == {"jobs": []}

        store.create(_spec(), run_id="j_old")
        newest = store.create(_spec(), run_id="j_new")
        rc = main(["status", "--data-dir", str(tmp_path)])
        human = capsys.readouterr()
        assert rc == 0
        assert human.out.splitlines()[0] == f"run_id: {newest.run_id}"
        assert human.out.splitlines()[1] == "NONE"
        assert STATUS_NO_ALPHA in human.out

        rc = main(["status", "--json", "--data-dir", str(tmp_path)])
        machine = capsys.readouterr()
        payload = json.loads(machine.out)
        assert payload["run_id"] == newest.run_id
        assert payload["research_outcome"] == "NONE"
    finally:
        server.shutdown()
```

Skill: `assert "latest job" in _skill_text().lower()` (or equivalent locked phrase).

E2E in `test_terminal_outcome_matches_cli_status` after the explicit-id human asserts:

```python
latest = _cli(real_daemon["data_dir"], "status")
assert latest.returncode == 0
assert latest.stdout.splitlines()[0] == f"run_id: {run_id}"
assert latest.stdout.splitlines()[1] == payload["research_outcome"]
```

- [x] **Step 2: Run tests to FAIL** (`run_id` still required)

- [x] **Step 3: Implement**

`EMPTY_STATUS_CUE` in `morning.py` (verbatim spec sentence + `"\n"`).

`status.add_argument("run_id", nargs="?")`

`run_status`: if `args.run_id` → existing get_run path. Else list_jobs; empty → cue / `{"jobs": []}`; else prepend `run_id:` for human, dump `jobs[0]` for `--json`.

Docs + Skill as in spec R4.

- [x] **Step 4: Full unit + e2e**

```bash
python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration
python3 -m pytest tests/e2e -m e2e
```

- [x] **Step 5: Commit**
