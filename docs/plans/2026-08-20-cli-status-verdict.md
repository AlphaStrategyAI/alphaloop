# CLI five-minute status verdict Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `alphaloop status` a five-minute morning verdict for humans, with `--json` for agents.

**Architecture:** `format_status_verdict` next to `morning_view` emits the locked cluster. Default `run_status` prints that string. `--json` keeps `json.dumps(morning_view, sort_keys=True)`. Cancel/resume stay JSON.

**Tech Stack:** Python 3.9+, argparse, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-cli-status-verdict.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. No FakeWorker in morning e2e.
- Do not shrink DSR `N`. Do not start soak jobs.

---

### Task 1: Formatter + CLI `--json`

**Files:**
- Modify: `src/alphaloop/runtime/morning.py`
- Modify: `src/alphaloop/cli/jobs.py`
- Modify: `docs/cli.md`, `README.md`, `docs/index.md`
- Modify: `src/alphaloop/skills/overnight-lab/SKILL.md`
- Test: `tests/runtime/test_morning.py`, `tests/runtime/test_cli_jobs.py`
- Test: `tests/skills/test_overnight_lab_skill.py`
- Test: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: `morning_view(...) -> dict`
- Produces: `format_status_verdict(view: dict[str, Any]) -> str`

- [ ] **Step 1: Write the failing tests**

In `tests/runtime/test_morning.py`:

```python
from alphaloop.runtime.morning import format_status_verdict

NO_ALPHA = "This status does not claim alpha or future profitability."

def test_format_status_verdict_found_cluster():
    text = format_status_verdict(
        {
            "research_outcome": "FOUND",
            "primary_evidence": "all required hard gates passed",
            "stop_reason": "all_gates_passed",
            "status": "completed",
            "queued_hypotheses": [],
            "qualifying_candidates": [
                {
                    "trial_id": "c_abc",
                    "kind": "momentum_12_1",
                    "parameters": {"lookback": 12},
                }
            ],
        }
    )
    lines = text.splitlines()
    assert lines[0] == "FOUND"
    assert lines[1] == (
        "FOUND means every required hard gate is present and passed. "
        "It is not a promise of alpha."
    )
    assert lines[2] == "Primary evidence: all required hard gates passed"
    assert lines[3] == "Stop reason: all_gates_passed"
    assert lines[4] == "Qualifying: c_abc · momentum_12_1 · lookback=12"
    assert lines[5] == "Job status: completed"
    assert lines[6] == NO_ALPHA
    assert text.endswith("\n")
    assert "target found" not in text.lower()
    assert "report_markdown" not in text


def test_format_status_verdict_none_omits_optional_lines():
    text = format_status_verdict(
        {
            "research_outcome": "NONE",
            "primary_evidence": None,
            "stop_reason": None,
            "status": "running",
            "queued_hypotheses": [],
            "qualifying_candidates": [{"trial_id": "c_skip"}],
        }
    )
    lines = text.splitlines()
    assert lines[0] == "NONE"
    assert lines[1] == (
        "Job status (queued, running, completed, failed, cancelled) "
        "is not the research conclusion."
    )
    assert lines[2] == "Primary evidence: (running or not yet terminal)"
    assert lines[3] == "Stop reason: (running or not yet terminal)"
    assert lines[4] == "Job status: running"
    assert "Next run:" not in text
    assert "Qualifying:" not in text


def test_format_status_verdict_queued_next_run():
    text = format_status_verdict(
        {
            "research_outcome": "NO_EVIDENCE",
            "primary_evidence": "dsr failed",
            "stop_reason": "hard_gate_failed",
            "status": "completed",
            "queued_hypotheses": [
                {"statement": "Try rsi. Not a claim of alpha."}
            ],
        }
    )
    assert "Next run: Try rsi. Not a claim of alpha." in text.splitlines()
    assert text.splitlines()[1].startswith("NO_EVIDENCE means")


def test_format_status_verdict_inconclusive_gloss():
    text = format_status_verdict(
        {
            "research_outcome": "INCONCLUSIVE",
            "primary_evidence": "no sealed gates.json",
            "stop_reason": "incomplete_evidence",
            "status": "completed",
        }
    )
    assert "incomplete" in text.splitlines()[1]
    assert "cannot produce FOUND" in text
```

In `tests/runtime/test_cli_jobs.py`, after the existing daemon helper pattern:

```python
import json
from alphaloop.cli.main import create_parser, main

def test_status_parser_has_json_flag():
    parser = create_parser()
    help_text = parser.format_help()
    assert "status" in help_text


def test_status_default_is_verdict_json_is_payload(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker, _spec

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    try:
        job = store.create(_spec())
        rc = main(["status", job.run_id, "--data-dir", str(tmp_path)])
        human = capsys.readouterr()
        assert rc == 0
        assert human.out.splitlines()[0] == "NONE"
        assert "This status does not claim alpha or future profitability." in human.out
        with pytest.raises(json.JSONDecodeError):
            json.loads(human.out)

        rc = main(["status", job.run_id, "--json", "--data-dir", str(tmp_path)])
        machine = capsys.readouterr()
        assert rc == 0
        payload = json.loads(machine.out)
        assert payload["run_id"] == job.run_id
        assert payload["research_outcome"] == "NONE"
        assert "report_markdown" in payload
    finally:
        server.shutdown()
```

Add `import pytest` if missing. Extend `test_skill_teaches_submit_and_poll_not_block` (or add):

```python
assert "alphaloop status RUN_ID --json" in _skill_text()
```

In `tests/e2e/test_morning_console.py` `test_terminal_outcome_matches_cli_status`:

```python
status = _cli(real_daemon["data_dir"], "status", "--json", run_id)
# existing json.loads assertions
human = _cli(real_daemon["data_dir"], "status", run_id)
assert human.returncode == 0
assert human.stdout.splitlines()[0] == payload["research_outcome"]
assert "Primary evidence:" in human.stdout
assert "This status does not claim alpha or future profitability." in human.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/runtime/test_morning.py::test_format_status_verdict_found_cluster tests/runtime/test_cli_jobs.py::test_status_default_is_verdict_json_is_payload -v
```

Expected: FAIL — `format_status_verdict` missing; default status still JSON.

- [ ] **Step 3: Write minimal implementation**

In `src/alphaloop/runtime/morning.py`:

```python
OUTCOME_GLOSS = {
    "FOUND": (
        "FOUND means every required hard gate is present and passed. "
        "It is not a promise of alpha."
    ),
    "NO_EVIDENCE": (
        "NO_EVIDENCE means a required hard gate failed. "
        "It is not a promise that alpha does not exist."
    ),
    "INCONCLUSIVE": (
        "INCONCLUSIVE means the evidence set is incomplete. "
        "Missing diagnostics cannot produce FOUND."
    ),
    "NONE": (
        "Job status (queued, running, completed, failed, cancelled) "
        "is not the research conclusion."
    ),
}

STATUS_NO_ALPHA = "This status does not claim alpha or future profitability."
_PENDING = "(running or not yet terminal)"


def _format_grid_row(parameters: Any) -> str:
    if not isinstance(parameters, dict) or not parameters:
        return "{}"
    return " ".join(f"{key}={parameters[key]}" for key in sorted(parameters))


def format_status_verdict(view: dict[str, Any]) -> str:
    outcome = str(view.get("research_outcome") or "NONE")
    lines = [outcome, OUTCOME_GLOSS.get(outcome, OUTCOME_GLOSS["NONE"])]
    primary = view.get("primary_evidence")
    lines.append(
        "Primary evidence: " + (primary if primary else _PENDING)
    )
    stop = view.get("stop_reason")
    lines.append("Stop reason: " + (stop if stop else _PENDING))
    queued = view.get("queued_hypotheses") or []
    if isinstance(queued, list) and queued:
        statement = queued[0].get("statement") if isinstance(queued[0], dict) else None
        if statement:
            lines.append("Next run: " + str(statement))
    qualifying = view.get("qualifying_candidates") or []
    if outcome == "FOUND" and isinstance(qualifying, list) and qualifying:
        row = qualifying[0] if isinstance(qualifying[0], dict) else {}
        trial = str(row.get("trial_id") or "gates.json")
        kind = str(row.get("kind") or "")
        params = _format_grid_row(row.get("parameters"))
        lines.append(f"Qualifying: {trial} · {kind} · {params}")
    lines.append("Job status: " + str(view.get("status") or ""))
    lines.append(STATUS_NO_ALPHA)
    return "\n".join(lines) + "\n"
```

In `src/alphaloop/cli/jobs.py` `register`:

```python
status.add_argument(
    "--json",
    action="store_true",
    help="print the full morning_view JSON",
)
```

Replace `run_status`:

```python
def run_status(args: argparse.Namespace) -> int:
    from alphaloop.runtime.morning import format_status_verdict

    result = _invoke(
        args.data_dir,
        lambda client: JobClient.get_run(client, args.run_id),
    )
    if result is None:
        return 2
    if args.json:
        print(json.dumps(result, sort_keys=True))
        return 0
    print(format_status_verdict(result), end="")
    return 0
```

Keep `run_cancel` / `run_resume` on `_run_action`.

Docs: `docs/cli.md` status section documents the cluster and `--json`.
README / `docs/index.md`: `alphaloop status RUN_ID` for humans;
`--json` for agents.

Skill workflow step 4:

```
4. **Poll** the morning page or `alphaloop status RUN_ID`. Parse JSON
   with `alphaloop status RUN_ID --json`. Do not block ...
```

- [ ] **Step 4: Run the new tests and the full suites**

```bash
python3 -m pytest tests/runtime/test_morning.py tests/runtime/test_cli_jobs.py tests/skills/test_overnight_lab_skill.py -v
python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration
python3 -m pytest tests/e2e -m e2e
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/requirements/2026-08-20-cli-status-verdict.md docs/plans/2026-08-20-cli-status-verdict.md src/alphaloop/runtime/morning.py src/alphaloop/cli/jobs.py src/alphaloop/skills/overnight-lab/SKILL.md docs/cli.md README.md docs/index.md tests/runtime/test_morning.py tests/runtime/test_cli_jobs.py tests/skills/test_overnight_lab_skill.py tests/e2e/test_morning_console.py
git commit -m "feat(cli): print a five-minute status verdict; keep --json for agents"
```
