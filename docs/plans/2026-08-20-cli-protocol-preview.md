# CLI protocol preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop preview --spec PATH` shows the compiled protocol without creating a job.

**Architecture:** `JobClient.preview_run` POSTs `/v1/jobs/preview`. CLI formats the same fields as packaged `#protocol-preview`, then `HOST_CONSTRAINT` and a locked no-alpha sentence. Empty status cue names preview-then-submit.

**Tech Stack:** Python 3.9+, argparse, pytest.

**Spec:** `docs/requirements/2026-08-20-cli-protocol-preview.md`

## Global Constraints

- Do not invent `FOUND` or a `run_id`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. No FakeWorker in morning e2e.
- Do not POST `/v1/jobs` from preview.

---

### Task 1: Client + CLI preview + empty cue

**Files:**
- Modify: `src/alphaloop/runtime/client.py`
- Modify: `src/alphaloop/cli/jobs.py`, `src/alphaloop/cli/main.py`
- Modify: `src/alphaloop/runtime/morning.py` (`EMPTY_STATUS_CUE`)
- Modify: `docs/cli.md`, `README.md`, `docs/index.md`
- Modify: `src/alphaloop/skills/overnight-lab/SKILL.md`
- Test: `tests/runtime/test_cli_jobs.py`
- Test: `tests/skills/test_overnight_lab_skill.py`

**Interfaces:**
- Consumes: `JobAPI.preview_run` / `POST /v1/jobs/preview`
- Produces: `JobClient.preview_run(spec: ResearchSpec) -> dict[str, Any]`
- Produces: `format_protocol_preview(body: dict[str, Any]) -> str`

- [x] **Step 1: Write the failing tests**

In `tests/runtime/test_cli_jobs.py`:

```python
def test_parser_has_runtime_commands():
    parser = create_parser()
    assert "preview" in parser.format_help()
    # existing start/submit/soak asserts stay


def test_preview_without_daemon_fails(tmp_path, capsys):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(_cached_spec().to_dict()), encoding="utf-8")
    rc = main(["preview", "--spec", str(spec_path), "--data-dir", str(tmp_path)])
    assert rc == 2
    assert "alphaloop start" in capsys.readouterr().err


def test_preview_shows_protocol_without_creating_a_job(tmp_path, capsys):
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
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(_cached_spec().to_dict()), encoding="utf-8")
    try:
        rc = main(["preview", "--spec", str(spec_path), "--data-dir", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "planned_n_trials:" in out
        assert "spec_id:" in out
        assert HOST_CONSTRAINT in out
        assert "Freeze with alphaloop submit --spec PATH" in out
        assert "This preview does not claim alpha or future profitability." in out
        assert "run_id:" not in out
        assert "target found" not in out.lower()
        assert api.list_jobs()["jobs"] == []

        rc = main(["preview", "--spec", str(spec_path), "--json", "--data-dir", str(tmp_path)])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["ok"] is True
        assert "run_id" not in payload
        assert payload["planned_n_trials"] >= 1
        assert api.list_jobs()["jobs"] == []
    finally:
        server.shutdown()


def test_preview_missing_dataset_is_not_ok_and_creates_no_job(tmp_path, capsys):
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
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    try:
        rc = main(["preview", "--spec", str(spec_path), "--data-dir", str(tmp_path)])
        captured = capsys.readouterr()
        assert rc == 2
        assert "dataset snapshot is required" in captured.out
        assert "Freeze with alphaloop submit" not in captured.out
        assert api.list_jobs()["jobs"] == []
    finally:
        server.shutdown()
```

Empty-status test already equals `EMPTY_STATUS_CUE`; after the constant changes it still passes if both update together. Add:

```python
assert "alphaloop preview --spec PATH" in EMPTY_STATUS_CUE
```

Skill: `assert "alphaloop preview" in lowered`.

- [x] **Step 2: Run to FAIL** (`preview` unknown)

- [x] **Step 3: Implement**

`JobClient.preview_run`: `_request("POST", "/v1/jobs/preview", spec.to_dict())`.

`format_protocol_preview` in `cli/jobs.py` (or `runtime/morning.py` next to `_format_grid_row` if imported). Grid lines use the same `k=v` sort as `_format_grid_row`.

`register` preview like submit. `run_preview` reads YAML like `run_submit`, calls `preview_run`, prints formatter or `--json`. Exit 0 iff `ok`.

`main.py` command set includes `"preview"`.

`EMPTY_STATUS_CUE` locked sentence from R3.

Docs + Skill: preview does not create a job; then submit to freeze.

- [x] **Step 4: Full unit + e2e**

- [x] **Step 5: Commit**
