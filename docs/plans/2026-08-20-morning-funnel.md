# Morning Elimination Funnel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seal every complete trial's evidence and show a search-wide elimination funnel in the morning payload, console, and `report.md`.

**Architecture:** `run_protocol` writes `evidence/trials/{candidate_id}.json` beside `gates.json`. `build_funnel` in `artifacts_io` aggregates those files (fallback: last `gates.json`). Morning view, report, and static console render counts plus per-gate tallies.

**Tech Stack:** existing protocol/runtime, pytest, Playwright, packaged static HTML/JS.

## Global Constraints

- Local-first overnight lab. Do not promise alpha. Do not invent `FOUND`.
- No FakeWorker in morning e2e. Do not change `HOST_CONSTRAINT`. Do not unfreeze `webui/`.
- `alphaloop.protocol` must not import `runtime`. Use `python3`.

---

### Task 1: Per-trial evidence + funnel aggregate

**Files:**
- Modify: `src/alphaloop/protocol/loop.py`
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Modify: `src/alphaloop/runtime/morning.py`
- Test: `tests/protocol/test_protocol_loop.py`, `tests/runtime/test_morning.py`, `tests/runtime/test_artifacts_io.py`

- [ ] **Step 1: Write failing tests**

In `tests/protocol/test_protocol_loop.py` inside `test_complete_fail_walks_the_frozen_parameter_grid`, after `len(ledger) == 3`:

```python
    trial_files = list((layout.evidence / "trials").glob("*.json"))
    assert len(trial_files) == 3
```

In `tests/runtime/test_morning.py`:

```python
def test_funnel_aggregates_trial_files_not_only_last_gates(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    run_dir = tmp_path / job.run_id
    (run_dir / "trial-ledger.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"trial_id": "c_a", "revision": "none"}),
                json.dumps({"trial_id": "c_b", "revision": "method"}),
                json.dumps({"trial_id": "c_c", "revision": "method"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    required = tuple(HardGateName(name) for name in job.spec.success_criteria.hard_gates)
    dsr_fail = evaluate_hard_gates(
        required,
        tuple(
            GateResult(name=name, passed=name is not HardGateName.DSR, detail={})
            for name in required
        ),
    )
    both_fail = evaluate_hard_gates(
        required,
        tuple(GateResult(name=name, passed=False, detail={}) for name in required),
    )
    evidence_dir = run_dir / "evidence"
    trials = evidence_dir / "trials"
    trials.mkdir(parents=True)
    (trials / "c_a.json").write_text(json.dumps(evidence_to_dict(dsr_fail)))
    (trials / "c_b.json").write_text(json.dumps(evidence_to_dict(dsr_fail)))
    (trials / "c_c.json").write_text(json.dumps(evidence_to_dict(both_fail)))
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(both_fail)))
    view = morning_view(store.complete_from_artifacts(job.run_id), tmp_path)
    assert view["funnel"]["n_evaluated"] == 3
    assert view["funnel"]["n_complete"] == 3
    assert view["funnel"]["n_passed"] == 0
    assert view["funnel"]["n_failed"] == 3
    assert view["funnel"]["failure_counts"]["dsr"] == 3
    assert view["funnel"]["dominant_failures"][0] == "dsr"
```

Keep `test_failed_gate_is_no_evidence` asserting last-only `dominant_failures` when `trials/` is absent.

In `tests/runtime/test_artifacts_io.py`:

```python
def test_report_includes_elimination_funnel(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    evidence = evaluate_hard_gates(
        (HardGateName.DSR,),
        (GateResult(name=HardGateName.DSR, passed=False, detail={}),),
    )
    trials = layout.evidence / "trials"
    trials.mkdir(parents=True)
    body = json.dumps(evidence_to_dict(evidence))
    (layout.evidence / "gates.json").write_text(body)
    (trials / "c_1.json").write_text(body)
    layout.trial_ledger.write_text(
        json.dumps({"trial_id": "c_1", "revision": "none"}) + "\n",
        encoding="utf-8",
    )
    write_report(layout, research_outcome="NO_EVIDENCE", stop_reason="hard_gate_failed")
    text = layout.report.read_text(encoding="utf-8")
    assert "## Elimination funnel" in text
    assert "evaluated: 1" in text
    assert "failed: 1" in text
    assert "dsr: 1" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/protocol/test_protocol_loop.py::test_complete_fail_walks_the_frozen_parameter_grid tests/runtime/test_morning.py::test_funnel_aggregates_trial_files_not_only_last_gates tests/runtime/test_artifacts_io.py::test_report_includes_elimination_funnel -q`

Expected: FAIL (no `trials/` dir / missing funnel keys / missing report section).

- [ ] **Step 3: Implement write + `build_funnel`**

In `loop.py`, extract `_write_evidence(layout, candidate_id, evidence)` that writes `gates.json` and `evidence/trials/{candidate_id}.json` with `evidence_to_dict`. Call it wherever `gates.json` is written, including after PBO attach.

In `artifacts_io.py`, add `build_funnel(layout) -> dict`. Load trial JSON via `evidence_from_dict`. If none, fall back to `gates.json`. Counts as in R2. `n_evaluated = max(unique ledger ids, n_complete)`.

`morning_view` sets `"funnel": build_funnel(layout)`.

`write_report` appends `## Elimination funnel` when `n_evaluated` or `n_complete` is positive.

- [ ] **Step 4: Run unit tests for this task**

Run: `python3 -m pytest tests/protocol/test_protocol_loop.py tests/runtime/test_morning.py tests/runtime/test_artifacts_io.py -q`

Expected: PASS.

---

### Task 2: Console + e2e

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `tests/runtime/test_static_console.py`
- Modify: `tests/e2e/test_morning_console.py`
- Modify: `mkdocs.yml`, `docs/webui.md`

- [ ] **Step 1: Write failing static + e2e tests**

In `test_packaged_guided_form_preview_grid_and_job_cards` or a sibling:

```python
    assert 'id="funnel-summary"' in html
    assert "failure_counts" in script
    assert "n_evaluated" in script
```

In `test_job_detail_while_running_or_later_legal_outcome`, after stop-reason:

```python
    assert "evaluated:" in page.locator("#funnel-summary").inner_text()
```

- [ ] **Step 2: Run static test to verify fail**

Run: `python3 -m pytest tests/runtime/test_static_console.py::test_packaged_guided_form_preview_grid_and_job_cards -q`

Expected: FAIL (`funnel-summary` missing).

- [ ] **Step 3: Implement console**

Add `<p id="funnel-summary"></p>` above `#funnel`. In `showJob`, set summary to `evaluated: N · passed: P · failed: F`. Funnel items: `name + " × " + count` from `failure_counts`. Revision renderer: `trial_id · revision · formatGridRow(parameters)`. Style `#funnel-summary` with the muted meta color. Mention the funnel in `docs/webui.md` first-release paragraph. Register req/plan in `mkdocs.yml`.

- [ ] **Step 4: Full unit + e2e**

Run: `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration -q`

Run: `python3 -m pytest tests/e2e -m e2e -q`

Expected: all passed (skip allowed).
