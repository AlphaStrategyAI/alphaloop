# Qualifying candidate signal glosses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Qualifying-candidate and FOUND-handoff kind display uses the same locked signal gloss as the guided form, without renaming payload `kind`.

**Architecture:** `_qualifying_entry` adds `kind_label` via `gloss_signal`. Report, packaged `#qualifying` / `#handoff`, and `format_status_verdict` print that label with a raw-`kind` fallback. No JS gloss table.

**Tech Stack:** Python 3.9+, packaged `app.js`, pytest.

**Spec:** `docs/requirements/2026-08-20-qualifying-glosses.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not rename payload `kind`. Do not change export receipt `Qualifying: {id}`.

---

### Task 1: kind_label + display surfaces

**Files:**
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Modify: `src/alphaloop/runtime/morning.py`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_morning.py`
- Test: `tests/runtime/test_static_console.py`

**Interfaces:**
- Consumes: `gloss_signal(kind: str) -> str`
- Produces: `qualifying_candidates[].kind_label: str | None`

- [x] **Step 1: Write the failing tests**

In `tests/runtime/test_morning.py` `test_passing_gates_found`:

```python
    assert view["qualifying_candidates"] == [
        {
            "trial_id": "gates.json",
            "kind": None,
            "kind_label": None,
            "parameters": {},
        }
    ]
```

In `test_qualifying_candidates_only_all_passed_trial_files`:

```python
    assert view["qualifying_candidates"] == [
        {
            "trial_id": "c_pass",
            "kind": "momentum_12_1",
            "kind_label": "momentum_12_1 — 12-1 momentum",
            "parameters": {"lookback": 126},
        }
    ]
```

In `test_format_status_verdict_found_cluster`, add `kind_label` to the
fixture and expect:

```python
    assert lines[4] == (
        "Qualifying: c_abc · momentum_12_1 — 12-1 momentum · lookback=12"
    )
```

Keep a fallback: passing the existing fixture without `kind_label`
MUST still print `momentum_12_1` (add a short extra assertion on a
second call, or a one-liner in the same test).

In `tests/runtime/test_static_console.py` `test_packaged_qualifying_candidates`:

```python
    assert "kind_label" in script
    assert "SIGNAL_GLOSS" not in script
```

- [x] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_morning.py::test_passing_gates_found tests/runtime/test_morning.py::test_qualifying_candidates_only_all_passed_trial_files tests/runtime/test_morning.py::test_format_status_verdict_found_cluster tests/runtime/test_static_console.py::test_packaged_qualifying_candidates -v
```

Expected: FAIL (`kind_label` missing from payload / script).

- [x] **Step 3: Write minimal implementation**

`artifacts_io._qualifying_entry`:

```python
from alphaloop.protocol.dsl import gloss_signal

    kind = payload.get("kind")
    kind_str = str(kind) if kind else None
    return {
        "trial_id": trial_id,
        "kind": kind_str,
        "kind_label": gloss_signal(kind_str) if kind_str else None,
        "parameters": parameters,
    }
```

`write_report` qualifying rows:

```python
            kind = row.get("kind") or ""
            label = row.get("kind_label") or kind
            parameters = row.get("parameters") or {}
            lines.append(f"{row['trial_id']} · {label} · {parameters}")
```

`format_status_verdict`:

```python
        kind = str(row.get("kind_label") or row.get("kind") or "")
```

`app.js` `fillQualifying` and `fillHandoff`:

```javascript
    (row.kind_label || row.kind || "")
```

`docs/webui.md`: qualifying candidate kinds use the same signal gloss
as the form.

Note: `alphaloop.runtime` already uses protocol helpers; adding
`gloss_signal` here does not create a protocol → runtime import.

- [x] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_morning.py tests/runtime/test_artifacts_io.py tests/runtime/test_static_console.py::test_packaged_qualifying_candidates -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git commit -m "feat: gloss qualifying candidate signal kinds"
```
