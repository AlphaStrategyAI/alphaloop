# Sealed report frozen-hypothesis signal gloss Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `report.md` (and `#report`) names the frozen `signal_mechanism` with the same locked gloss as the guided form.

**Architecture:** `write_report` interpolates `gloss_signal` on the frozen hypothesis line. YAML / EXAMPLE_SPEC / `morning_view` hypothesis tokens stay raw. `#report` already displays the sealed file.

**Tech Stack:** Python 3.9+, pytest, existing morning e2e.

**Spec:** `docs/requirements/2026-08-20-report-signal-gloss.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not rename `morning_view["hypothesis"].signal_mechanism`.

---

### Task 1: Gloss the frozen hypothesis line

**Files:**
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_artifacts_io.py`
- Test: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: `gloss_signal(kind: str) -> str` (already imported)
- Produces: `report.md` line `signal_mechanism: {gloss}`

- [x] **Step 1: Write the failing tests**

In `tests/runtime/test_artifacts_io.py`
`test_report_includes_frozen_hypothesis_and_n_trials`:

```python
    assert "signal_mechanism: momentum_12_1 — 12-1 momentum" in text
    assert "signal_mechanism: momentum_12_1\n" not in text
```

Keep `tests/runtime/test_static_console.py` EXAMPLE_SPEC assertion
`signal_mechanism: momentum_12_1` unchanged.

In `tests/e2e/test_morning_console.py` replay test, after reading
`report.md`:

```python
    assert "signal_mechanism: momentum_12_1 — 12-1 momentum" in report
```

After `#report` wait, also:

```python
    assert "momentum_12_1 — 12-1 momentum" in page.locator("#report").inner_text()
```

Load-example e2e MUST still assert raw YAML
`signal_mechanism: momentum_12_1`.

- [x] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_artifacts_io.py::test_report_includes_frozen_hypothesis_and_n_trials -v
```

Expected: FAIL (bare `signal_mechanism: momentum_12_1` still present).

- [x] **Step 3: Write minimal implementation**

In `write_report` frozen-hypothesis block:

```python
                f"signal_mechanism: {gloss_signal(hyp.signal_mechanism)}",
```

`docs/webui.md`: the sealed report names the frozen signal with the
same gloss as the form.

- [x] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_artifacts_io.py::test_report_includes_frozen_hypothesis_and_n_trials tests/runtime/test_static_console.py -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git commit -m "feat: gloss frozen signal_mechanism on the sealed report"
```
