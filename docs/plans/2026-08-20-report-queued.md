# Sealed report queued hypotheses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `report.md` / packaged `#report` lists queued follow-up statements after methodological revisions, or `none`.

**Architecture:** `build_queued_hypotheses` reads `recommendations.json`. `format_queued_line` is the trimmed `statement`. `write_report` emits `## Queued hypotheses` after revisions. Do not rewrite the recommendations file. Do not auto-execute.

**Tech Stack:** Python 3.9+, pytest, existing morning e2e.

**Spec:** `docs/requirements/2026-08-20-report-queued.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not rewrite `recommendations.json` or `trial-ledger.jsonl`. Do not execute queued economic revisions.

---

### Task 1: report section + docs

**Files:**
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_artifacts_io.py`
- Test: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Produces: `build_queued_hypotheses(layout) -> list[dict]`
- Produces: `format_queued_line(row: Mapping) -> str`

- [x] **Step 1: Write the failing tests**

In `tests/runtime/test_artifacts_io.py`:

```python
from alphaloop.runtime.artifacts_io import format_queued_line, write_report


def test_format_queued_line_uses_statement():
    assert (
        format_queued_line(
            {
                "statement": "No evidence for momentum_12_1 — 12-1 momentum. "
                "Try rsi — RSI. This is not a claim of alpha."
            }
        )
        == (
            "No evidence for momentum_12_1 — 12-1 momentum. "
            "Try rsi — RSI. This is not a claim of alpha."
        )
    )
    assert format_queued_line({}) == ""
    assert format_queued_line({"statement": "  "}) == ""


def test_report_includes_queued_hypotheses(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    layout.trial_ledger.write_text(
        json.dumps(
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
    layout.recommendations.write_text(
        json.dumps(
            {
                "queued_hypotheses": [
                    {
                        "statement": (
                            "No evidence for momentum_12_1 — 12-1 momentum. "
                            "Try rsi — RSI. This is not a claim of alpha."
                        )
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    write_report(layout, research_outcome="NO_EVIDENCE", stop_reason="hard_gate_failed")
    text = layout.report.read_text(encoding="utf-8")
    assert "## Methodological revisions" in text
    assert "## Queued hypotheses" in text
    assert text.index("## Methodological revisions") < text.index("## Queued hypotheses")
    assert (
        "No evidence for momentum_12_1 — 12-1 momentum. "
        "Try rsi — RSI. This is not a claim of alpha."
    ) in text
    assert text.split("## Queued hypotheses", 1)[1].strip().startswith(
        "No evidence for momentum_12_1 — 12-1 momentum."
    )


def test_report_queued_hypotheses_none_when_missing(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    write_report(layout, research_outcome="INCONCLUSIVE", stop_reason="incomplete_evidence")
    text = layout.report.read_text(encoding="utf-8")
    assert "## Queued hypotheses" in text
    assert text.split("## Queued hypotheses", 1)[1].strip().startswith("none")
```

In e2e `test_replay_rewrites_report`, after reading `report`:

```python
    assert "## Queued hypotheses" in report
```

- [x] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_artifacts_io.py::test_format_queued_line_uses_statement tests/runtime/test_artifacts_io.py::test_report_includes_queued_hypotheses tests/runtime/test_artifacts_io.py::test_report_queued_hypotheses_none_when_missing -v
```

Expected: FAIL (`format_queued_line` missing / heading missing).

- [x] **Step 3: Write minimal implementation**

In `artifacts_io.py`:

```python
def format_queued_line(row: Mapping[str, Any]) -> str:
    return str(row.get("statement") or "").strip()


def build_queued_hypotheses(layout: RunLayout) -> list[dict[str, Any]]:
    payload = _read_json_object(layout.recommendations)
    if payload is None:
        return []
    queued = payload.get("queued_hypotheses") or []
    return [dict(item) for item in queued if isinstance(item, dict)]
```

`write_report` after revisions:

```python
    queued = build_queued_hypotheses(layout)
    lines.extend(["", "## Queued hypotheses", ""])
    statements = [line for line in (format_queued_line(row) for row in queued) if line]
    if not statements:
        lines.append("none")
    else:
        lines.extend(statements)
```

`docs/webui.md`: the sealed report lists queued hypotheses (or `none`).

- [x] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_artifacts_io.py::test_format_queued_line_uses_statement tests/runtime/test_artifacts_io.py::test_report_includes_queued_hypotheses tests/runtime/test_artifacts_io.py::test_report_queued_hypotheses_none_when_missing tests/runtime/test_artifacts_io.py::test_report_includes_method_revisions -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: list queued hypotheses on the sealed report"
```
