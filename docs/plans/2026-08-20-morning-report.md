# Morning sealed report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show sealed `report.md` on the packaged morning page and keep Before bed beside Morning on a wide viewport.

**Architecture:** `morning_view` reads `layout.report` as `report_markdown`. Console `#report` uses `textContent`. CSS two-column `#console` at 960px. Outcome still comes only from the job record.

**Tech Stack:** Existing Job API, packaged static console, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-morning-report.md`

## Global Constraints

- Do not invent `FOUND`. Do not parse `report.md` to set `research_outcome`.
- `HOST_CONSTRAINT` locked. No `FakeWorker` in morning e2e. Help copy unchanged.

---

### Task 1: Payload

**Files:**
- Modify: `src/alphaloop/runtime/morning.py`
- Test: `tests/runtime/test_morning.py`

`morning_view` adds `report_markdown`. Missing file → `""`. Existing file → UTF-8 text.

```python
def test_morning_view_report_markdown_is_sealed_file_or_empty(tmp_path):
    from alphaloop.runtime.artifacts_io import write_report

    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    view = morning_view(job, tmp_path)
    assert view["report_markdown"] == ""
    layout = tmp_path / job.run_id
    from alphaloop.contracts.artifacts import RunLayout

    write_report(
        RunLayout(layout),
        research_outcome="NO_EVIDENCE",
        stop_reason="hard_gate_failed",
        spec=job.spec,
        n_trials=0,
    )
    view = morning_view(job, tmp_path)
    assert view["report_markdown"] == (layout / "report.md").read_text(encoding="utf-8")
    assert "This report does not claim alpha or future profitability." in view["report_markdown"]
    assert view["research_outcome"] == job.research_outcome.value
```

---

### Task 2: Console

**Files:** static `index.html`, `app.js`, `styles.css`; `tests/runtime/test_static_console.py`; `tests/e2e/test_morning_console.py`

`#report` after `#stop-reason`, before `#qualifying`. `fillReport` sets `textContent` from `job.report_markdown`. Wide CSS: `#console { grid-template-columns: 1fr 1fr }` with `#help` spanning both.

E2E: `#report` present on detail; after replay (report on disk), `#report` contains the locked no-alpha sentence.
