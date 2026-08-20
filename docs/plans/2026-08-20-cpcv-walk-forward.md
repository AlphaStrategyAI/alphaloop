# Combinatorial purged CV Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-release combinatorial purged CV (`S=6`, `k=2`) so the walk-forward gate cannot pass on a single lucky rolling partition.

**Architecture:** New pure function `combinatorial_purged_cv` beside `walk_forward_cv`. `run_hard_gates` ANDs CPCV into the existing `walk_forward` `GateResult` when the sample is long enough. DSR still uses walk-forward OOS. Morning lines copy the new detail keys.

**Tech Stack:** pandas, numpy, itertools, existing `compute_strategy_returns`, pytest, Playwright e2e.

## Global Constraints

- Local-first overnight lab. Do not promise alpha. Do not invent `FOUND`.
- No new `HardGateName`. No PBO. No `FakeWorker` in morning e2e.
- `alphaloop.protocol` must not import `runtime`.
- Use `python3`.

---

### Task 1: `combinatorial_purged_cv`

**Files:**
- Modify: `src/alphaloop/diagnostic/cv.py`
- Modify: `src/alphaloop/diagnostic/__init__.py`
- Test: `tests/diagnostic/test_cv.py`

- [ ] **Step 1: Failing tests** in `tests/diagnostic/test_cv.py`:

```python
from alphaloop.diagnostic.cv import combinatorial_purged_cv
from math import comb

def test_cpcv_not_evaluated_when_series_is_short():
    prices = _make_prices(80, drift=0.001)
    result = combinatorial_purged_cv(prices, _buy_and_hold)
    assert result.evaluated is False
    assert result.n_paths == 0


def test_cpcv_positive_drift_buy_and_hold_passes():
    prices = _make_prices(180, drift=0.003)
    result = combinatorial_purged_cv(prices, _buy_and_hold, embargo_size=1)
    assert result.evaluated is True
    assert result.n_groups == 6
    assert result.n_test_groups == 2
    assert result.n_paths == comb(6, 2)
    assert result.oos_sharpe_mean > 0
    assert result.oos_sharpe_median > 0
    assert result.passes is True


def test_cpcv_negative_drift_fails():
    prices = _make_prices(180, drift=-0.003)
    result = combinatorial_purged_cv(prices, _buy_and_hold, embargo_size=1)
    assert result.evaluated is True
    assert result.oos_sharpe_mean < 0
    assert result.passes is False
```

Reuse `_make_prices` / `_buy_and_hold` already in that file.

- [ ] **Step 2:** Run; expect import fail.

- [ ] **Step 3:** Implement `CombinatorialPurgedResult` and `combinatorial_purged_cv` as specified in the requirements. Split with `numpy.linspace`. Merge adjacent test groups into contiguous spans. Drop `embargo_size` bars from the start of each span (clipped to the span). Call `strategy_fn` on `prices.iloc[:span_end]` only. `passes = mean > min and median > min` when evaluated.

- [ ] **Step 4:** Tests pass. Export from `alphaloop.diagnostic`.

---

### Task 2: Wire into `walk_forward` gate + morning keys

**Files:**
- Modify: `src/alphaloop/protocol/gates.py`
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Test: `tests/protocol/test_gate_adapters.py`, `tests/runtime/test_artifacts_io.py`, `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Failing tests**

`test_walk_forward_detail_includes_regime_fields`: also assert `n_folds` int and, on 400 bars, `cpcv_passes is True`, `cpcv_n_paths == 15`.

New: short 80-bar WF gate has `n_folds` but not `cpcv_passes`.

`test_macd_walk_forward_job_records_regime_stable`: assert `"cpcv_passes"` in walk_forward detail (260 bars).

- [ ] **Step 2:** Run; expect fail.

- [ ] **Step 3:** In `run_hard_gates`, after computing `wf_result`, try `combinatorial_purged_cv` with the profile embargo/cost/periods. Add `n_folds` to `_detail`. When CPCV `evaluated`, AND into `passed` and copy `cpcv_*` fields. Extend `MORNING_DETAIL_KEYS`.

- [ ] **Step 4:** Register req/plan in `mkdocs.yml`. Unit + e2e. Commit.
