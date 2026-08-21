# Elimination funnel hard-gate glosses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Morning `#funnel` labels and `report.md` elimination lines use the same locked hard-gate gloss as the guided form, without renaming funnel payload keys.

**Architecture:** `build_funnel` keeps token keys and adds a parallel `dominant_failure_labels` list via `gloss_hard_gate`. `write_report` interpolates the gloss. Packaged `fillFunnel` prints those labels. No JS gloss table.

**Tech Stack:** Python 3.9+, packaged `app.js`, pytest, existing morning e2e.

**Spec:** `docs/requirements/2026-08-20-funnel-glosses.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not rename `failure_counts` keys or `dominant_failures` tokens.
- Do not gloss qualifying `kind` this cycle.

---

### Task 1: Funnel labels + report + console

**Files:**
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_artifacts_io.py`
- Test: `tests/runtime/test_morning.py`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: `gloss_hard_gate(name: str) -> str`
- Produces: `build_funnel(...)["dominant_failure_labels"]: list[str]` parallel to `dominant_failures`

- [x] **Step 1: Write the failing tests**

In `tests/runtime/test_artifacts_io.py`, extend
`test_report_includes_elimination_funnel`:

```python
    assert "dsr — Deflated Sharpe Ratio: 1" in text
    assert "dsr: 1\n" not in text
```

(Replace the existing `assert "dsr: 1" in text`.)

In `tests/runtime/test_morning.py`, extend
`test_funnel_aggregates_trial_files_not_only_last_gates` and
`test_failed_gate_is_no_evidence`:

```python
    assert view["funnel"]["dominant_failures"][0] == "dsr"
    assert view["funnel"]["dominant_failure_labels"][0] == (
        "dsr — Deflated Sharpe Ratio"
    )
```

Empty-funnel cases (`test_missing_gates_is_inconclusive`,
`test_passing_gates_found`) MUST assert
`view["funnel"]["dominant_failure_labels"] == []`.

In `tests/runtime/test_static_console.py`, extend
`test_packaged_funnel_bars`:

```python
    assert "dominant_failure_labels" in script
    assert "HARD_GATE_GLOSS" not in script
```

In `tests/e2e/test_morning_console.py`
`test_macd_walk_forward_job_records_regime_stable`, after `#evidence`:

```python
    funnel_text = page.locator("#funnel").inner_text()
    assert "walk_forward ×" not in funnel_text
    if funnel_text.strip() != "none":
        assert "walk-forward OOS" in funnel_text
```

- [x] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_artifacts_io.py::test_report_includes_elimination_funnel tests/runtime/test_morning.py::test_funnel_aggregates_trial_files_not_only_last_gates tests/runtime/test_morning.py::test_failed_gate_is_no_evidence tests/runtime/test_static_console.py::test_packaged_funnel_bars -v
```

Expected: FAIL (`dominant_failure_labels` missing; report still has `dsr: 1`).

- [x] **Step 3: Write minimal implementation**

In `build_funnel`, after computing `dominant_failures`:

```python
    return {
        "n_evaluated": n_evaluated,
        "n_complete": n_complete,
        "n_passed": n_passed,
        "n_failed": n_failed,
        "n_incomplete": max(0, n_evaluated - n_complete),
        "failure_counts": failure_counts,
        "dominant_failures": dominant_failures,
        "dominant_failure_labels": [
            gloss_hard_gate(name) for name in dominant_failures
        ],
    }
```

`write_report` elimination lines:

```python
        for name in funnel["dominant_failures"]:
            lines.append(
                f"{gloss_hard_gate(name)}: {funnel['failure_counts'][name]}"
            )
```

In `src/alphaloop/webui/static/app.js` `fillFunnel`:

```javascript
  const names = funnel.dominant_failures;
  const labels = funnel.dominant_failure_labels || [];
  const counts = funnel.failure_counts || {};
  // ...
  names.forEach(function (name, i) {
    const count = counts[name] || 0;
    const li = document.createElement("li");
    li.className = "funnel-fail";
    const label = document.createElement("span");
    label.textContent = (labels[i] || name) + " × " + count;
    // track / fill unchanged
  });
```

`docs/webui.md`: the elimination funnel uses the same hard-gate gloss
as the form.

- [x] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_artifacts_io.py::test_report_includes_elimination_funnel tests/runtime/test_morning.py tests/runtime/test_static_console.py::test_packaged_funnel_bars -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/artifacts_io.py src/alphaloop/webui/static/app.js docs/webui.md tests/runtime/test_artifacts_io.py tests/runtime/test_morning.py tests/runtime/test_static_console.py tests/e2e/test_morning_console.py
git commit -m "feat: gloss hard-gate names on the elimination funnel"
```
