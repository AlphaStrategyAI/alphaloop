# Morning console .asb export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a human export a FOUND ledger candidate as `.asb` from the packaged morning page, using the same lock as the CLI.

**Architecture:** Extract `export_found_asb` from `cli/export.py`. `JobAPI.export_run` writes `{run_dir}/exports/{id}.asb`. Daemon POST `/v1/jobs/{id}/export`. Console `export-asb` buttons on FOUND qualifying `c_*` rows.

**Tech Stack:** Existing bundle writer, Job API, packaged static console, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-console-asb-export.md`

## Global Constraints

- Do not invent `FOUND`. `assert_exportable` stays the gate.
- `HOST_CONSTRAINT` locked. No `FakeWorker` in morning e2e. No Python in `.asb`.

---

### Task 1: Shared writer + JobAPI + HTTP

**Files:**
- Create: `src/alphaloop/runtime/asb_export.py`
- Modify: `src/alphaloop/cli/export.py`
- Modify: `src/alphaloop/runtime/api.py`
- Modify: `src/alphaloop/runtime/daemon.py`
- Test: `tests/runtime/test_api.py`, `tests/runtime/test_http.py`, `tests/cli/test_export.py`

Move ledger scan + payload + `write_asb` into:

```python
def export_found_asb(
    *,
    store: JobStore,
    data_dir: Path,
    run_id: str,
    candidate_id: str,
    output: Path,
) -> Path:
```

Reject ids with `/`, `\\`, `..`. CLI `run_export` calls it. `JobAPI.export_run` writes to `RunLayout(self.data_dir / run_id).run_dir / "exports" / f"{candidate_id}.asb"`.

POST action `export` reads JSON `candidate_id`. 409 on `ExportNotAllowed`.

---

### Task 2: Console

**Files:** static `index.html`, `app.js`, `styles.css`; `tests/runtime/test_static_console.py`; `tests/e2e/test_morning_console.py`

`#export-status`. `fillQualifying` adds `button.export-asb` only when `job.research_outcome === "FOUND"` and `trial_id` starts with `c_`. POST `/v1/jobs/{id}/export`. Show `exported_path` on `#export-status`.
