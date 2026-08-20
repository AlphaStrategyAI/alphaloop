# Queued Follow-up Hypotheses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After `NO_EVIDENCE`, queue one constrained counterpart-kind hypothesis and let the morning page load it into the editor without submitting.

**Architecture:** `protocol/recommend.py` maps kind → counterpart. `run_protocol` writes `recommendations.json` only when returning `NO_EVIDENCE` and the queue is empty. Packaged JS `load-queued` fills the form; Preview remains required to freeze.

**Tech Stack:** existing protocol/runtime, pytest, Playwright, packaged static page.

## Global Constraints

- Local-first overnight lab. Do not promise alpha. Do not invent `FOUND`.
- Do not execute an economic change in the same run. Do not expand a failed method grid.
- No FakeWorker in morning e2e. Do not change `HOST_CONSTRAINT`. Use `python3`.
- `alphaloop.protocol` must not import `runtime`.

---

### Task 1: Counterpart + queue on NO_EVIDENCE

**Files:**
- Create: `src/alphaloop/protocol/recommend.py`, `tests/protocol/test_recommend.py`
- Modify: `src/alphaloop/protocol/loop.py`, `tests/protocol/test_protocol_loop.py`

- [ ] **Step 1: Write failing tests**

`tests/protocol/test_recommend.py`:

```python
from alphaloop.protocol.recommend import counterpart_kind, followup_hypotheses

def test_counterpart_kind_table():
    assert counterpart_kind("momentum_12_1") == "rsi"
    assert counterpart_kind("roc") == "rsi"
    assert counterpart_kind("macd") == "rsi"
    assert counterpart_kind("atr_breakout") == "rsi"
    assert counterpart_kind("rsi") == "momentum_12_1"
    assert counterpart_kind("bollinger_zscore") == "momentum_12_1"
    assert counterpart_kind("ohlr_4_pct") == "momentum_12_1"
    assert counterpart_kind("pairs_spread") == "rsi"
    assert counterpart_kind("parkinson_hist_vol") is None
    assert counterpart_kind("obv_slope") is None
```

In `test_protocol_loop.py`:

- After complete-fail momentum walk, assert queued `[0].signal_mechanism == "rsi"`, `queued_reason == "economic_change_queued"`, and `"not a claim of alpha"` in statement.lower().
- `test_protocol_found_from_passing_gates` still `queued_hypotheses == []`.
- Change `test_frozen_grid_does_not_call_revision_proposer` to count proposer calls (`== 0`) and assert no `macd` from the proposer.
- Keep `test_existing_recommendations_are_not_truncated`.

- [ ] **Step 2: Run tests to verify fail**

Run: `python3 -m pytest tests/protocol/test_recommend.py tests/protocol/test_protocol_loop.py::test_complete_fail_walks_the_frozen_parameter_grid -q`

Expected: FAIL (module missing / empty queue).

- [ ] **Step 3: Implement recommend + loop write**

`followup_hypotheses(spec, evidence) -> list[dict]`. Dominant failed required gates joined for the statement. `run_protocol` helper writes the list on every `NO_EVIDENCE` return when the existing queue is empty.

- [ ] **Step 4: Run protocol tests**

Run: `python3 -m pytest tests/protocol/test_recommend.py tests/protocol/test_protocol_loop.py -q`

Expected: PASS.

---

### Task 2: Load into editor + e2e

**Files:**
- Modify: `src/alphaloop/webui/static/app.js`, `src/alphaloop/webui/static/styles.css`
- Modify: `tests/runtime/test_static_console.py`, `tests/e2e/test_morning_console.py`
- Modify: `mkdocs.yml`

- [ ] **Step 1: Write failing UI tests**

Static: `"load-queued" in script`. E2E: submit example, write `recommendations.json` with an `rsi` follow-up, open detail, click `.load-queued`, assert `#field-signal-mechanism` is `rsi`, `#submit-job` disabled, still one job card.

- [ ] **Step 2: Implement JS**

Replace queued `fillList` with list items that include `button.load-queued`. `loadQueuedHypothesis` copies statement, economic_logic, signal_mechanism, market_scope, market_profile, benchmark, hard_gates into the form, rewrites YAML, `previewedYaml = null`, `setSubmitEnabled(false)`. No POST.

- [ ] **Step 3: Unit + e2e**

Run: `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration -q`

Run: `python3 -m pytest tests/e2e -m e2e -q`
