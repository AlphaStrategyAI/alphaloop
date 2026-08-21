# CLI status elimination funnel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop status` / `replay` five-minute cluster names evaluated/passed/failed counts and dominant-failure glosses.

**Architecture:** `format_status_verdict` reads `view["funnel"]` and emits `Funnel:` plus `Dominant:` lines. `replay_view` adds `funnel` from `build_funnel`. Zero/missing omits the lines. Failure count keys stay tokens.

**Tech Stack:** Python 3.9+, pytest, existing morning e2e.

**Spec:** `docs/requirements/2026-08-20-status-funnel.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not rewrite `trial-ledger.jsonl`. Do not execute queued economic revisions.

---

### Task 1: funnel lines + replay payload

**Files:**
- Modify: `src/alphaloop/runtime/morning.py`
- Modify: `docs/cli.md`
- Test: `tests/runtime/test_morning.py`
- Test: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: `view["funnel"]` (`n_evaluated`, `n_passed`, `n_failed`, `n_incomplete`, `failure_counts`, `dominant_failures`, `dominant_failure_labels`)
- Consumes: `build_funnel(layout) -> dict`

- [ ] **Step 1: Write the failing tests**

In `tests/runtime/test_morning.py`:

```python
def test_format_status_verdict_prints_funnel():
    text = format_status_verdict(
        {
            "research_outcome": "NO_EVIDENCE",
            "primary_evidence": "dsr — Deflated Sharpe Ratio failed",
            "stop_reason": "hard_gate_failed",
            "status": "completed",
            "funnel": {
                "n_evaluated": 3,
                "n_passed": 0,
                "n_failed": 3,
                "n_incomplete": 0,
                "failure_counts": {"dsr": 3},
                "dominant_failures": ["dsr"],
                "dominant_failure_labels": ["dsr — Deflated Sharpe Ratio"],
            },
            "revisions": [],
            "queued_hypotheses": [],
        }
    )
    lines = text.splitlines()
    assert "Funnel: evaluated=3 passed=0 failed=3 incomplete=0" in lines
    assert "Dominant: dsr — Deflated Sharpe Ratio × 3" in lines
    assert lines.index("Stop reason: hard_gate_failed") < lines.index(
        "Funnel: evaluated=3 passed=0 failed=3 incomplete=0"
    )
    assert "dsr × 3" not in text


def test_replay_view_includes_funnel(tmp_path):
    from alphaloop.contracts.artifacts import RunLayout

    layout = RunLayout(tmp_path / "j_replay")
    layout.run_dir.mkdir()
    view = replay_view(layout, research_outcome="INCONCLUSIVE", status="completed")
    assert view["funnel"]["n_evaluated"] == 0
    assert view["funnel"]["dominant_failures"] == []
```

In `test_format_status_verdict_none_omits_optional_lines`, add:

```python
    assert "Funnel:" not in text
    assert "Dominant:" not in text
```

In e2e status test after `human = _cli(..., "status", run_id)`:

```python
    if (payload.get("funnel") or {}).get("n_evaluated"):
        assert "Funnel:" in human.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_morning.py::test_format_status_verdict_prints_funnel tests/runtime/test_morning.py::test_replay_view_includes_funnel tests/runtime/test_morning.py::test_format_status_verdict_none_omits_optional_lines -v
```

Expected: FAIL (`Funnel:` missing / `funnel` missing on replay_view).

- [ ] **Step 3: Write minimal implementation**

In `morning.py`, after stop reason and before revisions:

```python
    funnel = view.get("funnel") or {}
    if isinstance(funnel, Mapping):
        n_eval = int(funnel.get("n_evaluated") or 0)
        n_pass = int(funnel.get("n_passed") or 0)
        n_fail = int(funnel.get("n_failed") or 0)
        n_inc = int(funnel.get("n_incomplete") or 0)
        if n_eval or n_pass or n_fail or n_inc:
            lines.append(
                f"Funnel: evaluated={n_eval} passed={n_pass} "
                f"failed={n_fail} incomplete={n_inc}"
            )
            counts = funnel.get("failure_counts") or {}
            labels = list(funnel.get("dominant_failure_labels") or [])
            names = list(funnel.get("dominant_failures") or [])
            for i, name in enumerate(names):
                label = labels[i] if i < len(labels) else str(name)
                count = counts.get(name, 0) if isinstance(counts, dict) else 0
                lines.append(f"Dominant: {label} × {count}")
```

Need `Mapping` import if not present (`from typing import Any, Mapping, Optional`).

`replay_view`: `"funnel": funnel`.

`docs/cli.md`: optional funnel counts and dominant-failure glosses.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_morning.py::test_format_status_verdict_prints_funnel tests/runtime/test_morning.py::test_replay_view_includes_funnel tests/runtime/test_morning.py::test_format_status_verdict_none_omits_optional_lines tests/runtime/test_morning.py::test_format_status_verdict_found_cluster tests/runtime/test_morning.py::test_format_status_verdict_glosses_revisions -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: print elimination funnel on CLI status"
```
