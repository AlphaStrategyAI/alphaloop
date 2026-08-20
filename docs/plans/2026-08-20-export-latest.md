# CLI export latest job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop export CANDIDATE_ID -o PATH` without `--run-id` exports the latest job.

**Architecture:** `--run-id` optional. `run_export` uses `store.list_jobs()[0].run_id` when omitted. Empty list → stderr + 2.

**Tech Stack:** argparse, JobStore, pytest.

**Spec:** `docs/requirements/2026-08-20-export-latest.md`

## Global Constraints

- Do not invent `FOUND`. Do not change `assert_exportable` / Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- No auto-export. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not change the four-line receipt.

---

### Task 1: Optional `--run-id`

**Files:**
- Modify: `src/alphaloop/cli/export.py`
- Modify: `docs/cli.md`, `src/alphaloop/skills/overnight-lab/SKILL.md`, `mkdocs.yml`
- Test: `tests/cli/test_export.py`
- Test: `tests/skills/test_overnight_lab_skill.py` (if skill text changes)

- [ ] **Step 1: Failing tests**

```python
def test_export_without_run_id_uses_latest_found_job(tmp_path, capsys):
    older = _found_job(tmp_path, candidate_id="c_old")
    newest = _found_job(tmp_path, candidate_id="c1")
    out = tmp_path / "latest.asb"
    rc = main(["export", "c1", "--data-dir", str(tmp_path), "--output", str(out)])
    assert rc == 0
    assert zipfile.is_zipfile(out)
    assert capsys.readouterr().out.splitlines()[0] == "FOUND"


def test_export_without_run_id_empty_store(tmp_path, capsys):
    rc = main(["export", "c1", "--data-dir", str(tmp_path), "--output", str(tmp_path / "x.asb")])
    assert rc == 2
    err = capsys.readouterr().err
    assert err == "error: no overnight job yet\n"
    assert "FOUND" not in capsys.readouterr().out
```

Note: second `readouterr` is empty; capture once.

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/cli/test_export.py::test_export_without_run_id_uses_latest_found_job tests/cli/test_export.py::test_export_without_run_id_empty_store -v
```

- [ ] **Step 3: Implement**

`--run-id` not required. Resolve from `list_jobs()[0]` or locked empty error.

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(cli): export without --run-id uses the latest job"
```
