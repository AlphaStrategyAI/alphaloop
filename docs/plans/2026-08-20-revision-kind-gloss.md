# Methodological revision signal gloss Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Morning `#revisions` and `report.md` name the repaired signal kind with the same locked gloss as the form, without rewriting the trial ledger.

**Architecture:** `build_method_revisions` copies `revision == "method"` ledger rows and adds `kind_label` via `gloss_signal`. `format_revision_line` joins trial, revision token, glossed kind, and params. Packaged JS and `write_report` use that line. No JS gloss table.

**Tech Stack:** Python 3.9+, packaged `app.js`, pytest, existing morning e2e.

**Spec:** `docs/requirements/2026-08-20-revision-kind-gloss.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not rewrite `trial-ledger.jsonl`. Do not execute queued economic revisions.

---

### Task 1: kind_label + line format + report

**Files:**
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Modify: `src/alphaloop/runtime/morning.py`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_artifacts_io.py`
- Test: `tests/runtime/test_morning.py`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Produces: `build_method_revisions(layout) -> list[dict]`
- Produces: `format_revision_line(row: Mapping) -> str`

- [x] **Step 1: Write the failing tests**

In `tests/runtime/test_artifacts_io.py`:

```python
from alphaloop.runtime.artifacts_io import format_revision_line, write_report


def test_format_revision_line_glosses_kind():
    assert format_revision_line(
        {
            "trial_id": "c_2",
            "revision": "method",
            "kind": "momentum_12_1",
            "kind_label": "momentum_12_1 — 12-1 momentum",
            "parameters": {"window": 21},
        }
    ) == "c_2 · method · momentum_12_1 — 12-1 momentum · window=21"
    assert format_revision_line(
        {"trial_id": "c_2", "revision": "method", "parameters": {}}
    ) == "c_2 · method · {}"


def test_report_includes_method_revisions(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    layout.trial_ledger.write_text(
        json.dumps({"trial_id": "c_1", "revision": "none", "kind": "momentum_12_1"})
        + "\n"
        + json.dumps(
            {
                "trial_id": "c_2",
                "revision": "method",
                "kind": "momentum_12_1",
                "parameters": {"window": 21},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    write_report(layout, research_outcome="NO_EVIDENCE", stop_reason="hard_gate_failed")
    text = layout.report.read_text(encoding="utf-8")
    assert "## Methodological revisions" in text
    assert "c_2 · method · momentum_12_1 — 12-1 momentum · window=21" in text
    assert "c_1 · none" not in text
```

In `test_revisions_and_queued_hypotheses`, add `"kind": "momentum_12_1"` to the method row and:

```python
    assert view["revisions"][0]["kind_label"] == "momentum_12_1 — 12-1 momentum"
```

In `test_packaged_qualifying_candidates` or a nearby static test:

```python
    rev_at = script.find('getElementById("revisions")')
    assert rev_at != -1
    assert "kind_label" in script[rev_at : rev_at + 500]
    assert "SIGNAL_GLOSS" not in script
```

In e2e `test_bollinger_job_records_method_trials`, after reading ledger rows:

```python
    _open_job_detail(page)
    if any(row.get("revision") == "method" for row in rows):
        page.wait_for_selector("#revisions")
        assert "Bollinger z-score" in page.locator("#revisions").inner_text()
```

- [x] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_artifacts_io.py::test_format_revision_line_glosses_kind tests/runtime/test_artifacts_io.py::test_report_includes_method_revisions tests/runtime/test_morning.py::test_revisions_and_queued_hypotheses -v
```

Expected: FAIL (`format_revision_line` missing / `kind_label` missing).

- [x] **Step 3: Write minimal implementation**

In `artifacts_io.py`:

```python
def _format_parameters(parameters: Any) -> str:
    if not isinstance(parameters, dict) or not parameters:
        return "{}"
    return " ".join(f"{key}={parameters[key]}" for key in sorted(parameters))


def format_revision_line(row: Mapping[str, Any]) -> str:
    trial = str(row.get("trial_id") or "")
    revision = str(row.get("revision") or "")
    label = str(row.get("kind_label") or row.get("kind") or "")
    parts = [part for part in (trial, revision, label) if part]
    parts.append(_format_parameters(row.get("parameters")))
    return " · ".join(parts)


def build_method_revisions(layout: RunLayout) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _ledger_rows(layout):
        if row.get("revision") != "method":
            continue
        kind = row.get("kind")
        kind_str = str(kind) if kind else None
        payload = dict(row)
        payload["kind_label"] = gloss_signal(kind_str) if kind_str else None
        rows.append(payload)
    return rows
```

`write_report` after qualifying:

```python
    revisions = build_method_revisions(layout)
    lines.extend(["", "## Methodological revisions", ""])
    if not revisions:
        lines.append("none")
    else:
        lines.extend(format_revision_line(row) for row in revisions)
```

`morning.py`: import `build_method_revisions`; `_load_revisions` returns it.

`app.js` next to `formatGridRow`:

```javascript
function formatRevisionRow(row) {
  const parts = [
    row.trial_id || "",
    row.revision || "",
    row.kind_label || row.kind || "",
  ].filter(Boolean);
  parts.push(formatGridRow(row.parameters));
  return parts.join(" · ");
}
```

`fillList(..., job.revisions, formatRevisionRow)`.

`docs/webui.md`: revision lines name the repaired signal with the same gloss as the form.

- [x] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_artifacts_io.py::test_format_revision_line_glosses_kind tests/runtime/test_artifacts_io.py::test_report_includes_method_revisions tests/runtime/test_morning.py::test_revisions_and_queued_hypotheses tests/runtime/test_morning.py::test_revisions_omit_first_frozen_grid_point tests/runtime/test_static_console.py::test_packaged_qualifying_candidates -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: gloss repaired signal kinds on methodological revisions"
```
