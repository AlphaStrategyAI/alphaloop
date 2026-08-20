# Probability of Backtest Overfitting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When two or more trials have been scored, block `FOUND` if CSCV shows the in-sample winner is usually the out-of-sample loser.

**Architecture:** Pure `probability_of_backtest_overfitting` in `alphaloop.diagnostic.pbo`. `run_protocol` collects per-trial net returns and, on a would-be `FOUND` with `N>=2`, ANDs PBO into the DSR (else walk-forward) `GateResult`. Complete hard-gate failure still does not walk the rest of the grid.

**Tech Stack:** numpy, pandas, itertools, existing GateEvidence, pytest.

## Global Constraints

- Local-first overnight lab. Do not promise alpha. Do not invent `FOUND`.
- No new `HardGateName`. No FakeWorker in morning e2e.
- `alphaloop.protocol` must not import `runtime`.
- Use `python3`.

---

### Task 1: `probability_of_backtest_overfitting`

**Files:**
- Create: `src/alphaloop/diagnostic/pbo.py`
- Modify: `src/alphaloop/diagnostic/__init__.py`
- Test: `tests/diagnostic/test_pbo.py`

- [ ] **Step 1: Failing tests**

```python
from math import comb
from alphaloop.diagnostic.pbo import probability_of_backtest_overfitting

def test_pbo_not_evaluated_for_one_strategy():
    idx = pd.bdate_range("2020-01-01", periods=180)
    one = pd.Series(0.001, index=idx)
    result = probability_of_backtest_overfitting([one])
    assert result.evaluated is False

def test_pbo_identical_series_passes():
    idx = pd.bdate_range("2020-01-01", periods=180)
    a = pd.Series(0.001, index=idx)
    result = probability_of_backtest_overfitting([a, a.copy(), a.copy()])
    assert result.evaluated is True
    assert result.n_paths == comb(6, 3)
    assert result.n_strategies == 3
    assert result.pbo < 0.5
    assert result.passes is True

def test_pbo_fails_when_is_winner_is_oos_loser():
    # three series: early-strong/late-weak, flat, early-weak/late-strong
    ...
    assert result.evaluated is True
    assert result.pbo >= 0.5
    assert result.passes is False
```

- [ ] **Step 2:** Run; expect import fail.

- [ ] **Step 3:** Implement CSCV PBO with `S=6`, IS size 3, rank 1 = lowest OOS Sharpe, overfit if `rank/N < 0.5`, pass if `pbo < 0.5`. Reuse `_cpcv_group_ranges` and `_annualized_sharpe`.

- [ ] **Step 4:** Export from `alphaloop.diagnostic`. Tests pass.

---

### Task 2: Attach in `run_protocol`

**Files:**
- Modify: `src/alphaloop/protocol/loop.py`
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Test: `tests/protocol/test_protocol_loop.py`, `tests/runtime/test_artifacts_io.py`

- [ ] Keep `test_failed_gate_does_not_walk_the_parameter_grid` and `test_found_stops_after_first_passing_trial`.

- [ ] Add `test_pbo_failure_blocks_found_after_method_repair` that monkeypatches PBO to `passes=False` after `_IncompleteThenPass`; outcome `NO_EVIDENCE`; runner called twice.

- [ ] Collect `strategy_returns` every trial. On `found`, if `len>=2`, attach PBO, rewrite `gates.json`, return `NO_EVIDENCE` when not `all_passed`.

- [ ] Extend `MORNING_DETAIL_KEYS`. Register req/plan in `mkdocs.yml`.
