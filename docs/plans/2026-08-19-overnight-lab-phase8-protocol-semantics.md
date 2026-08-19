# Overnight Lab Phase 8 — Protocol Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each grid trial's hard gates see that trial's lagged target-weight returns, treat complete passing evidence as `FOUND` even when the budget is already exhausted, and have the production worker pass a monotonic clock plus the spec cost budget into `run_protocol`.

**Architecture:** Phase 7 already iterates `method_parameter_grid` and honors `should_continue`, but `strategy_returns` is still raw asset `pct_change`, and `should_continue` checks budget before `FOUND`. Phase 8 adds a tiny `protocol/returns.py` helper, reorders stop rules, and wires `clock` / `remaining_cost_usd` from `runtime/worker.py`. No checkpoint resume, dataset snapshot, Web submit, or CI in this plan.

**Tech Stack:** Python 3.9+, pytest, pandas (existing), Phase 1 contracts, Phase 3–7 protocol.

## Global Constraints

- `FOUND` only from complete `GateEvidence` via `outcome_from_evidence`. `llm_judge` is not a hard gate.
- JobStatus and ResearchOutcome stay separate.
- Method repairs may continue; economic-logic / signal_mechanism / market_scope / benchmark / hard-gate changes are queued, not executed in the same run.
- Negative OOS, cost failure, failed hard gate, regime instability, and expanding an already failed search do not justify more parameter search (`FORBIDDEN_CONTINUE_REASONS`).
- Complete passing evidence stops the loop (`FOUND`). Complete failing evidence stops the loop (`NO_EVIDENCE`).
- Frozen `ResearchSpec` is never mutated.
- `alphaloop.protocol` must not import `alphaloop.live`, `alphaloop.webui`, or `alphaloop.runtime`.
- Do not rewrite diagnostic or engineer math.
- Do not invent a token/cost meter. `remaining_cost_usd` is the spec value or an explicit kwarg.
- Tests use synthetic prices only (no network).
- Source of truth: `docs/requirements/product-positioning-requirements.md` §6 and `docs/plans/2026-08-19-overnight-lab-remaining-work.md`.

## File Structure

- Create: `src/alphaloop/protocol/returns.py` — lagged weight × asset returns
- Modify: `src/alphaloop/protocol/loop.py` — use helper for `strategy_returns`; recompute remaining time from `clock` after each trial
- Modify: `src/alphaloop/protocol/stop.py` — `FOUND` before budget
- Modify: `src/alphaloop/protocol/__init__.py` — export `compute_strategy_returns` if tests import it from the package
- Modify: `src/alphaloop/runtime/worker.py` — pass `clock` and `remaining_cost_usd`
- Test: `tests/protocol/test_returns.py`
- Test: `tests/protocol/test_stop.py`
- Test: `tests/protocol/test_protocol_loop.py`
- Test: `tests/runtime/test_worker.py`
- Modify: `tests/runtime/test_import_graph.py` only if a new protocol file would import a forbidden package (it must not)

## Out of scope (later plans)

- Checkpoint payload resume (`load_latest_complete` driving skipped trials)
- Writing `manifest.yaml`, `candidates.parquet`, `report.md`
- Content-addressed dataset fail-closed; removing synthetic prices
- Packaged Web submit / preflight / progress polling
- CI pytest workflow, soak, usability study

---

### Task 1: Lagged strategy returns helper

**Files:**
- Create: `src/alphaloop/protocol/returns.py`
- Test: `tests/protocol/test_returns.py`

**Interfaces:**
- Consumes: two `pandas.Series` aligned on the same index (`prices`, `weights`)
- Produces: `compute_strategy_returns(prices: pd.Series, weights: pd.Series) -> pd.Series`
  - `asset_ret = prices.pct_change().fillna(0.0)`
  - return `weights.shift(1).fillna(0.0) * asset_ret`
  - Result index equals `prices.index`
  - Do not look ahead: today's return uses yesterday's weight

- [ ] **Step 1: Write the failing test**

Create `tests/protocol/test_returns.py`:

```python
from __future__ import annotations

import pandas as pd

from alphaloop.protocol.returns import compute_strategy_returns


def test_lagged_weights_times_asset_returns():
    prices = pd.Series([100.0, 110.0, 121.0], index=pd.RangeIndex(3))
    weights = pd.Series([0.0, 1.0, 1.0], index=prices.index)
    out = compute_strategy_returns(prices, weights)
    assert list(out.index) == list(prices.index)
    assert out.iloc[0] == 0.0
    assert out.iloc[1] == 0.0
    assert abs(float(out.iloc[2]) - 0.1) < 1e-12


def test_all_ones_is_not_raw_pct_change_on_first_bar():
    prices = pd.Series([100.0, 110.0, 121.0], index=pd.RangeIndex(3))
    weights = pd.Series([1.0, 1.0, 1.0], index=prices.index)
    out = compute_strategy_returns(prices, weights)
    raw = prices.pct_change().fillna(0.0)
    assert out.iloc[0] == 0.0
    assert abs(float(out.iloc[1]) - float(raw.iloc[1])) < 1e-12
    assert not out.equals(raw)
```

- [ ] **Step 2: Run the new tests, expect FAIL**

Run: `python -m pytest tests/protocol/test_returns.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'alphaloop.protocol.returns'` (or `ImportError` for `compute_strategy_returns`).

- [ ] **Step 3: Write minimal implementation**

Create `src/alphaloop/protocol/returns.py`:

```python
from __future__ import annotations

import pandas as pd


def compute_strategy_returns(prices: pd.Series, weights: pd.Series) -> pd.Series:
    asset_ret = prices.pct_change().fillna(0.0)
    lagged = weights.reindex(prices.index).shift(1).fillna(0.0)
    return lagged * asset_ret
```

If tests import from `alphaloop.protocol`, add the name to `src/alphaloop/protocol/__init__.py`. Prefer importing from `alphaloop.protocol.returns` in tests so `__init__.py` can stay unchanged.

- [ ] **Step 4: Run the tests, expect PASS**

Run: `python -m pytest tests/protocol/test_returns.py -v`

Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/protocol/returns.py tests/protocol/test_returns.py src/alphaloop/protocol/__init__.py
git commit -m "feat(protocol): compute lagged strategy returns from target weights"
```

---

### Task 2: `run_protocol` feeds lagged returns into gates

**Files:**
- Modify: `src/alphaloop/protocol/loop.py`
- Test: `tests/protocol/test_protocol_loop.py`

**Interfaces:**
- Consumes: existing `_strategy_fn_for(trial_doc, prices)` and `compute_strategy_returns`
- Produces: `run_hard_gates` / `gate_runner` receives
  `strategy_returns=compute_strategy_returns(primary_prices, _strategy_fn_for(trial_doc, prices)(primary_prices))`
  instead of `primary_prices.pct_change().fillna(0.0)`
- Walk-forward continues to receive `strategy_fn=_strategy_fn_for(trial_doc, prices)`
- Grid still mutates `trial_doc.parameters` only

- [ ] **Step 1: Write the failing test**

Add to `tests/protocol/test_protocol_loop.py` (reuse `_spec`, `_prices`, `_all_pass`):

```python
def test_gate_runner_receives_lagged_weight_returns_not_raw_prices(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    captured = {}

    def runner(required, **kwargs):
        captured["strategy_returns"] = kwargs["strategy_returns"]
        captured["strategy_fn"] = kwargs["strategy_fn"]
        return _all_pass(required, **kwargs)

    prices = _prices()
    run_protocol(
        _spec(),
        layout,
        prices=prices,
        buy_hold_prices=prices["AAPL"],
        benchmark_prices=prices["AAPL"],
        gate_runner=runner,
    )
    raw = prices["AAPL"].pct_change().fillna(0.0)
    assert "strategy_returns" in captured
    assert not captured["strategy_returns"].equals(raw)
    weights = captured["strategy_fn"](prices["AAPL"])
    expected = weights.shift(1).fillna(0.0) * raw
    pd.testing.assert_series_equal(
        captured["strategy_returns"],
        expected,
        check_names=False,
    )
```

- [ ] **Step 2: Run the new test, expect FAIL**

Run: `python -m pytest tests/protocol/test_protocol_loop.py::test_gate_runner_receives_lagged_weight_returns_not_raw_prices -v`

Expected: FAIL on `assert not captured["strategy_returns"].equals(raw)` (today they are equal).

- [ ] **Step 3: Write minimal implementation**

In `src/alphaloop/protocol/loop.py`, import `compute_strategy_returns` and replace the `strategy_returns=` argument inside the trial loop:

```python
from alphaloop.protocol.returns import compute_strategy_returns
```

```python
        primary = trial_doc.universe[0]
        primary_prices = prices.get(primary, buy_hold_prices)
        strategy_fn = _strategy_fn_for(trial_doc, prices)
        weights = strategy_fn(primary_prices)
        stop_evidence: Optional[GateEvidence] = None
        try:
            evidence = runner(
                required,
                prices=primary_prices,
                strategy_returns=compute_strategy_returns(primary_prices, weights),
                buy_hold_prices=buy_hold_prices,
                benchmark_prices=benchmark_prices,
                secondary_frames=secondary_frames,
                n_trials=n_trials,
                profile=profile,
                seed=spec.seed,
                strategy_fn=strategy_fn,
            )
```

Do not change ledger append, `n_trials` increment, or stop-reason handling in this task.

- [ ] **Step 4: Run protocol tests, expect PASS**

Run: `python -m pytest tests/protocol/test_protocol_loop.py tests/protocol/test_returns.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/protocol/loop.py tests/protocol/test_protocol_loop.py
git commit -m "feat(protocol): evaluate hard gates on lagged strategy returns"
```

---

### Task 3: Complete passing evidence beats exhausted budget

**Files:**
- Modify: `src/alphaloop/protocol/stop.py`
- Modify: `src/alphaloop/protocol/loop.py`
- Test: `tests/protocol/test_stop.py`
- Test: `tests/protocol/test_protocol_loop.py`

**Interfaces:**
- Consumes: existing `should_continue(*, remaining_time_s, remaining_cost_usd, last_evidence, proposed_kind, stop_reason) -> StopDecision`
- Produces: when `last_evidence` is complete and `all_passed`, return `StopDecision(continue_search=False, queue_for_human=False, reason="found")` **before** the budget branch. Keep economic, forbidden-reason, hard-gate-failed, and method-repair branches.
- `run_protocol` must recompute `remaining_time` from `clock` **after** the trial (before `should_continue`) so a long trial can exhaust the budget. If that trial produced complete passing evidence, the outcome is still `FOUND`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/protocol/test_stop.py`:

```python
def test_complete_pass_beats_exhausted_budget():
    evidence = GateEvidence(
        results=(GateResult(name=HardGateName.DSR, passed=True, detail={}),),
        required=(HardGateName.DSR,),
    )
    decision = should_continue(
        remaining_time_s=0,
        remaining_cost_usd=0.0,
        last_evidence=evidence,
        proposed_kind=RevisionKind.METHOD,
        stop_reason=None,
    )
    assert decision.continue_search is False
    assert decision.queue_for_human is False
    assert decision.reason == "found"
```

Add to `tests/protocol/test_protocol_loop.py`:

```python
def test_found_after_trial_when_clock_exhausts_during_gates(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    ticks = {"n": 0}

    def clock():
        ticks["n"] += 1
        if ticks["n"] == 1:
            return 0.0
        return 1000.0

    result = run_protocol(
        _spec(time_budget_s=10),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_all_pass,
        clock=clock,
    )
    assert result.research_outcome is ResearchOutcome.FOUND
    assert result.job_status is JobStatus.COMPLETED
```

Keep `test_budget_exhaustion_after_incomplete_is_inconclusive` unchanged (incomplete evidence plus exhausted clock stays `INCONCLUSIVE`).

- [ ] **Step 2: Run the new tests, expect FAIL**

Run:

```
python -m pytest tests/protocol/test_stop.py::test_complete_pass_beats_exhausted_budget tests/protocol/test_protocol_loop.py::test_found_after_trial_when_clock_exhausts_during_gates -v
```

Expected: FAIL with `decision.reason == "budget_exhausted"` and/or `research_outcome is INCONCLUSIVE`.

- [ ] **Step 3: Write minimal implementation**

In `src/alphaloop/protocol/stop.py`, move the complete-pass branch above the budget check. Target order:

1. `proposed_kind is ECONOMIC` → queue
2. `stop_reason in FORBIDDEN_CONTINUE_REASONS` → stop with that reason
3. complete + `all_passed` → `found`
4. `remaining_time_s <= 0 or remaining_cost_usd <= 0` → `budget_exhausted`
5. complete + not `all_passed` + METHOD + no stop_reason → `hard_gate_failed`
6. else `method_repair`

In `src/alphaloop/protocol/loop.py`, after the `try/except` that produces `evidence` / `stop_evidence`, recompute remaining time before `should_continue`:

```python
        if clock is not None:
            remaining_time = float(spec.time_budget_s - clock())
        decision = should_continue(
            remaining_time_s=remaining_time,
            remaining_cost_usd=remaining_cost,
            last_evidence=stop_evidence,
            proposed_kind=RevisionKind.METHOD,
            stop_reason=None,
        )
```

Keep the start-of-iteration budget guard so a new trial is not started after the clock is already exhausted. That guard must not apply to the trial that just finished.

- [ ] **Step 4: Run stop + loop tests, expect PASS**

Run: `python -m pytest tests/protocol/test_stop.py tests/protocol/test_protocol_loop.py -v`

Expected: PASS. Confirm `test_budget_exhausted_stops` still passes (no evidence, zero time → `budget_exhausted`).

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/protocol/stop.py src/alphaloop/protocol/loop.py tests/protocol/test_stop.py tests/protocol/test_protocol_loop.py
git commit -m "fix(protocol): keep FOUND when the clock expires during a passing trial"
```

---

### Task 4: Production worker passes clock and cost budget

**Files:**
- Modify: `src/alphaloop/runtime/worker.py`
- Test: `tests/runtime/test_worker.py`

**Interfaces:**
- Consumes: existing `_run_protocol(spec, layout)` which currently calls `run_protocol` with only `prices`, `buy_hold_prices`, `benchmark_prices`
- Produces: `_run_protocol` passes
  - `clock=lambda: time.monotonic() - started` where `started = time.monotonic()` captured once before `run_protocol`
  - `remaining_cost_usd=spec.cost_budget_usd`
- Do not pass a fake `revision_proposer`. Do not synthesize a declining cost meter.

- [ ] **Step 1: Write the failing test**

Add to `tests/runtime/test_worker.py`:

```python
def test_run_worker_passes_clock_and_cost_budget(monkeypatch, tmp_path):
    captured = {}

    def fake_run_protocol(spec, layout, **kwargs):
        captured["kwargs"] = kwargs
        captured["spec"] = spec
        return None

    monkeypatch.setattr("alphaloop.protocol.loop.run_protocol", fake_run_protocol)
    run_id = "j_clock"
    layout = RunLayout(tmp_path / run_id)
    layout.run_dir.mkdir()
    spec = _spec()
    layout.research_spec.write_text(
        yaml.safe_dump(spec.to_dict()),
        encoding="utf-8",
    )
    assert run_worker(run_id, tmp_path) == 0
    assert callable(captured["kwargs"]["clock"])
    assert captured["kwargs"]["remaining_cost_usd"] == spec.cost_budget_usd
    first = captured["kwargs"]["clock"]()
    second = captured["kwargs"]["clock"]()
    assert second >= first
```

- [ ] **Step 2: Run the new test, expect FAIL**

Run: `python -m pytest tests/runtime/test_worker.py::test_run_worker_passes_clock_and_cost_budget -v`

Expected: FAIL with `KeyError: 'clock'` (or `remaining_cost_usd`).

- [ ] **Step 3: Write minimal implementation**

In `src/alphaloop/runtime/worker.py`, add `import time` and change `_run_protocol`:

```python
def _run_protocol(spec: ResearchSpec, layout: RunLayout) -> None:
    from alphaloop.protocol.loop import run_protocol

    prices, buy_hold, benchmark = _load_or_synthesize_prices(layout, spec)
    started = time.monotonic()
    run_protocol(
        spec,
        layout,
        prices=prices,
        buy_hold_prices=buy_hold,
        benchmark_prices=benchmark,
        clock=lambda: time.monotonic() - started,
        remaining_cost_usd=spec.cost_budget_usd,
    )
```

- [ ] **Step 4: Run worker tests, expect PASS**

Run: `python -m pytest tests/runtime/test_worker.py tests/runtime/test_import_graph.py -v`

Expected: PASS. Import graph still forbids `alphaloop.protocol` from importing `runtime`.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/worker.py tests/runtime/test_worker.py
git commit -m "feat(runtime): pass monotonic clock and cost budget into run_protocol"
```

---

### Task 5: Regression sweep and docs pointers

**Files:**
- Modify: `docs/plans/overnight-research-lab-refactor.md` Phase 7 “later plans” sentence only if this file is not already linked from Phase 8
- Modify: `docs/requirements/product-positioning-requirements.md` §13 — add Phase 8 link if missing
- Modify: `mkdocs.yml` — already listed if the remaining-work PR added it; do not duplicate

**Interfaces:**
- No code API. Confirm protocol + worker tests still pass together.

- [ ] **Step 1: Run the focused regression**

Run:

```
python -m pytest tests/protocol tests/runtime/test_worker.py tests/runtime/test_import_graph.py tests/contracts/test_gates.py -v
```

Expected: PASS. Do not run `tests/integration` (`-m integration` stays deselected by default).

- [ ] **Step 2: Point docs at this plan if the remaining-work PR did not already**

In `docs/requirements/product-positioning-requirements.md` §13, after the Phase 7 paragraph, ensure this sentence exists:

```markdown
Phase 8 implementation plan:
[`docs/plans/2026-08-19-overnight-lab-phase8-protocol-semantics.md`](../plans/2026-08-19-overnight-lab-phase8-protocol-semantics.md).
```

- [ ] **Step 3: Commit only if docs changed**

```bash
git add docs/requirements/product-positioning-requirements.md docs/plans/overnight-research-lab-refactor.md mkdocs.yml
git commit -m "docs: point remaining-work Phase 8 at protocol semantics plan"
```

If `git status` is clean, skip the commit.
