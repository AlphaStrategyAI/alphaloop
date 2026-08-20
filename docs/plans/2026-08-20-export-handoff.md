# CLI export FOUND handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Successful `alphaloop export` prints a FOUND receipt (token, qualifying id, path, no-alpha), with `--json` for agents.

**Architecture:** `format_export_handoff` next to the other morning formatters. `run_export` prints it after `export_found_asb`. Failures stay stderr + 2.

**Tech Stack:** Python 3.9+, argparse, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-export-handoff.md`

## Global Constraints

- Do not invent `FOUND`. Do not change `assert_exportable` / Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- No auto-export. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs.

---

### Task 1: Receipt + `--json`

**Files:**
- Modify: `src/alphaloop/runtime/morning.py`
- Modify: `src/alphaloop/cli/export.py`
- Modify: `docs/cli.md`, `src/alphaloop/skills/overnight-lab/SKILL.md`, `mkdocs.yml`
- Test: `tests/runtime/test_morning.py`
- Test: `tests/cli/test_export.py`
- Test: `tests/e2e/test_morning_console.py`
- Test: `tests/skills/test_overnight_lab_skill.py` (if skill mentions export receipt)

- [x] **Step 1: Failing tests**

```python
def test_format_export_handoff_cluster():
    text = format_export_handoff(candidate_id="c_abc", exported_path="/tmp/out.asb")
    lines = text.splitlines()
    assert lines[0] == "FOUND"
    assert lines[1] == "Qualifying: c_abc"
    assert lines[2] == "Exported: /tmp/out.asb"
    assert lines[3] == "This export does not claim alpha or future profitability."
    assert text.endswith("\n")
    assert "target found" not in text.lower()
```

Extend `test_export_writes_asb_zip` with capsys: first line FOUND, Qualifying: c1, Exported:, EXPORT_NO_ALPHA, json.loads raises.

Add `--json` parser + payload test.

E2E FOUND branch: `exported.stdout.splitlines()[0] == "FOUND"`.

- [x] **Step 2: FAIL**

```bash
python3 -m pytest tests/cli/test_export.py::test_export_writes_asb_zip tests/runtime/test_morning.py::test_format_export_handoff_cluster -v
```

- [x] **Step 3: Implement**

`EXPORT_NO_ALPHA` + `format_export_handoff`. Export parser `--json`. `run_export` prints cluster or JSON.

- [x] **Step 4: Tests pass**

- [x] **Step 5: Commit**

```bash
git commit -m "feat(cli): print a FOUND handoff receipt on export"
```
