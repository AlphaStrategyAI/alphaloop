# Net-of-cost validation and method search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply profile `cost_bps` to every hard-gate return series, make walk-forward embargoed and history-aware, and search 12-1 momentum on Jegadeesh–Titman formation lookbacks.

**Architecture:** One return function (`compute_strategy_returns`) owns lag + turnover cost. `run_protocol` and `walk_forward_cv` both use it. The overnight walk-forward adapter chooses embargo and window sizes from the market profile. `momentum_12_1` gains a `lookback` argument; `method_parameter_grid` lists 12m/9m/6m formation with skip=21.

**Tech Stack:** Existing pandas protocol/diagnostic/engineer modules, pytest, Playwright e2e against a real daemon.

**Spec:** `docs/requirements/2026-08-19-net-of-cost-validation.md`

## Global Constraints

- Do not promise alpha. `FOUND` only from complete `GateEvidence`.
- `cost_bps` is one-way; cost return = turnover × `cost_bps / 10_000`.
- Position at bar `t` remains `weights.shift(1)` (no look-ahead).
- `cost_bps=0` and `embargo_size=0` preserve existing unit-test series and fold counts.
- Morning e2e: real Chromium + real daemon; no `FakeWorker`; do not invent `FOUND`.
- `llm_judge` is not a gate. `alphaloop.live` stays frozen.
- Plans live under `docs/plans/` (repo convention).
- Insufficient walk-forward history → missing gate result → `INCONCLUSIVE`, not fake pass.

---

### Task 1: Net-of-cost `compute_strategy_returns`

**Files:**
- Modify: `src/alphaloop/protocol/returns.py`
- Modify: `tests/protocol/test_returns.py`
- Modify: `src/alphaloop/protocol/loop.py` (pass `profile.cost_bps`)

**Interfaces:**
- Consumes: lagged weights, `pct_change`, `cost_bps`
- Produces:

```python
def compute_strategy_returns(
    prices: pd.Series,
    weights: pd.Series,
    *,
    cost_bps: float = 0.0,
) -> pd.Series:
```

- [ ] **Step 1: Write the failing tests**

Append to `tests/protocol/test_returns.py`:

```python
def test_zero_cost_matches_gross_lagged_returns():
    prices = pd.Series([100.0, 110.0, 121.0], index=pd.RangeIndex(3))
    weights = pd.Series([0.0, 1.0, 1.0], index=prices.index)
    gross = compute_strategy_returns(prices, weights)
    net = compute_strategy_returns(prices, weights, cost_bps=0.0)
    pd.testing.assert_series_equal(gross, net)


def test_turnover_pays_one_way_cost_bps():
    prices = pd.Series([100.0, 100.0, 100.0], index=pd.RangeIndex(3))
    weights = pd.Series([0.0, 1.0, 0.0], index=prices.index)
    out = compute_strategy_returns(prices, weights, cost_bps=10.0)
    # bar 0: position 0, turnover 0
    # bar 1: position 1 (lag of weight 1), turnover |1-0|=1, cost=10/10000
    # bar 2: position 0, turnover |0-1|=1, cost=10/10000
    assert out.iloc[0] == 0.0
    assert abs(float(out.iloc[1]) - (-0.001)) < 1e-12
    assert abs(float(out.iloc[2]) - (-0.001)) < 1e-12
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/protocol/test_returns.py::test_turnover_pays_one_way_cost_bps -v`

Expected: FAIL — `cost_bps` not accepted or costs not subtracted.

- [ ] **Step 3: Implement**

```python
def compute_strategy_returns(
    prices: pd.Series,
    weights: pd.Series,
    *,
    cost_bps: float = 0.0,
) -> pd.Series:
    asset_ret = prices.pct_change().fillna(0.0)
    position = weights.reindex(prices.index).shift(1).fillna(0.0)
    gross = position * asset_ret
    turnover = position.diff().abs().fillna(0.0)
    cost = turnover * (float(cost_bps) / 10_000.0)
    return gross - cost
```

In `run_protocol`, change the `strategy_returns=` call to:

```python
        strategy_returns=compute_strategy_returns(
            primary_prices, weights, cost_bps=profile.cost_bps
        ),
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/protocol/test_returns.py tests/protocol/test_protocol_loop.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/protocol/returns.py src/alphaloop/protocol/loop.py tests/protocol/test_returns.py
git commit -m "feat(protocol): subtract profile turnover costs from strategy returns"
```

---

### Task 2: History-aware embargoed walk-forward

**Files:**
- Modify: `src/alphaloop/diagnostic/cv.py`
- Modify: `src/alphaloop/protocol/gates.py`
- Modify: `tests/diagnostic/test_cv.py`
- Modify: `tests/protocol/test_gate_adapters.py`

**Interfaces:**
- Consumes: `compute_strategy_returns`, `embargo_size`, `cost_bps`
- Produces: `walk_forward_cv(..., embargo_size: int = 0, cost_bps: float = 0.0)`

Fold geometry: train `[i, i+train_size)`, embargo next `embargo_size` bars, test next `test_size` bars. Call `strategy_fn(prices.iloc[:test_end])` once per fold. Slice net returns to train/test index ranges.

Need at least `train_size + embargo_size + test_size` bars. Default `embargo_size=0` keeps current fold counts for existing tests **except** `strategy_fn` now sees history through test end (buy-and-hold tests still pass).

Overnight adapter helper in `gates.py`:

```python
def _walk_forward_windows(n: int, periods_per_year: int) -> tuple[int, int, int]:
    embargo = max(1, periods_per_year // 52)
    year = periods_per_year
    quarter = max(1, periods_per_year // 4)
    if n >= year + quarter + embargo:
        return year, quarter, embargo
    train = max(20, n // 2)
    test = max(10, n // 8)
    if n < train + embargo + test:
        raise ValueError(
            f"Need at least train+embargo+test = {train + embargo + test} bars, got {n}"
        )
    return train, test, embargo
```

- [ ] **Step 1: Write the failing tests**

In `tests/diagnostic/test_cv.py`:

```python
def test_walk_forward_strategy_fn_sees_history_through_test(tmp_path=None):
    prices = _make_prices(400)
    seen: list[int] = []

    def spy(series: pd.Series) -> pd.Series:
        seen.append(len(series))
        return pd.Series(1.0, index=series.index)

    walk_forward_cv(
        prices, spy, train_size=200, test_size=50, embargo_size=5, step_size=50
    )
    assert seen
    assert all(length >= 200 + 5 + 50 for length in seen)


def test_walk_forward_embargo_gaps_train_and_test():
    prices = _make_prices(400)
    result = walk_forward_cv(
        prices, _buy_and_hold, train_size=200, test_size=50, embargo_size=5, step_size=55
    )
    assert result.n_folds >= 1
    for fold in result.folds:
        train_end_i = prices.index.get_loc(fold.train_end)
        test_start_i = prices.index.get_loc(fold.test_start)
        assert int(test_start_i) - int(train_end_i) - 1 == 5
```

In `tests/protocol/test_gate_adapters.py`:

```python
def test_walk_forward_adapter_passes_profile_cost_and_embargo():
    prices = _prices(80)
    required = (HardGateName.WALK_FORWARD,)
    with mock.patch("alphaloop.protocol.gates.walk_forward_cv") as wf:
        wf.return_value = mock.Mock(passes=True, oos_sharpe_mean=0.1)
        run_hard_gates(
            required,
            prices=prices,
            strategy_returns=_returns(prices),
            buy_hold_prices=prices,
            benchmark_prices=prices,
            secondary_frames=None,
            n_trials=1,
            profile=get_profile("us-equity-daily"),
            seed=1,
            strategy_fn=_strategy_fn,
        )
        kwargs = wf.call_args.kwargs
        assert kwargs["cost_bps"] == 5.0
        assert kwargs["embargo_size"] >= 1
```

```python
def test_dsr_detail_records_cost_bps():
    prices = _prices()
    evidence = run_hard_gates(
        (HardGateName.DSR,),
        prices=prices,
        strategy_returns=_returns(prices),
        buy_hold_prices=prices,
        benchmark_prices=prices,
        secondary_frames=None,
        n_trials=1,
        profile=get_profile("us-equity-daily"),
        seed=1,
        strategy_fn=_strategy_fn,
    )
    assert evidence.results[0].detail["cost_bps"] == 5.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/diagnostic/test_cv.py::test_walk_forward_embargo_gaps_train_and_test tests/protocol/test_gate_adapters.py::test_walk_forward_adapter_passes_profile_cost_and_embargo -v`

Expected: FAIL — `embargo_size` / `cost_bps` missing.

- [ ] **Step 3: Implement `walk_forward_cv`**

Import `compute_strategy_returns` from `alphaloop.protocol.returns`.

Loop:

```python
    required = train_size + embargo_size + test_size
    if len(prices) < required:
        raise ValueError(
            f"Need at least train_size+embargo_size+test_size = {required} bars, "
            f"got {len(prices)}"
        )
    ...
    while i + train_size + embargo_size + test_size <= len(prices):
        test_start_i = i + train_size + embargo_size
        test_end_i = test_start_i + test_size
        history = prices.iloc[:test_end_i]
        all_weights = strategy_fn(history)
        net = compute_strategy_returns(history, all_weights, cost_bps=cost_bps)
        train_returns = net.iloc[i : i + train_size]
        test_returns = net.iloc[test_start_i:test_end_i]
        ...
        i += step_size
```

`step_size` still defaults to `test_size`.

In `_run_one` for `WALK_FORWARD`, replace the train/test constants with `_walk_forward_windows(len(prices), periods)` and pass `embargo_size` and `cost_bps=profile.cost_bps`.

In `_detail` / DSR+vs rows, after building `GateResult`, merge `{"cost_bps": profile.cost_bps}` into `detail` for every gate in `run_hard_gates` (set on the result dict in `_run_one` via a `cost_bps` argument already in scope).

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/diagnostic/test_cv.py tests/protocol/test_gate_adapters.py -v`

Expected: PASS. Existing fold-count test still uses `embargo_size=0`.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/diagnostic/cv.py src/alphaloop/protocol/gates.py tests/diagnostic/test_cv.py tests/protocol/test_gate_adapters.py
git commit -m "feat(diagnostic): embargoed history-aware walk-forward with profile costs"
```

---

### Task 3: Jegadeesh–Titman formation lookbacks

**Files:**
- Modify: `src/alphaloop/engineer/momentum.py`
- Modify: `src/alphaloop/protocol/search.py`
- Modify: `tests/engineer/test_momentum.py`
- Modify: `tests/protocol/test_search.py`

**Interfaces:**
- Consumes: `lookback`, `skip`
- Produces: `momentum_12_1(prices, skip=21, lookback=252)` and grid `({}, {lookback:126, skip:21}, {lookback:189, skip:21})`

- [ ] **Step 1: Write the failing tests**

In `tests/engineer/test_momentum.py`:

```python
def test_momentum_12_1_lookback_changes_warmup():
    idx = pd.date_range("2018-01-01", periods=400, freq="B")
    p = pd.Series(np.linspace(100, 200, 400), index=idx)
    short = momentum_12_1(p, skip=21, lookback=126)
    long = momentum_12_1(p, skip=21, lookback=252)
    assert short.iloc[126 + 21] != 0 or short.iloc[150] != 0
    assert (long.iloc[: 126 + 20] == 0).all()
```

(Implement the assertion so the shorter lookback is non-zero before the 12-month warmup: `assert short.iloc[160] > 0` on a pure uptrend; `assert long.iloc[160] == 0`.)

In `tests/protocol/test_search.py` replace `assert {"skip": 42} in grid` with:

```python
def test_grid_starts_with_defaults():
    grid = method_parameter_grid("momentum_12_1")
    assert grid[0] == {}
    assert {"lookback": 126, "skip": 21} in grid
    assert {"lookback": 189, "skip": 21} in grid
    assert len(grid) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/protocol/test_search.py::test_grid_starts_with_defaults tests/engineer/test_momentum.py::test_momentum_12_1_lookback_changes_warmup -v`

Expected: FAIL.

- [ ] **Step 3: Implement**

In `momentum_12_1`:

```python
def momentum_12_1(prices: pd.Series, skip: int = 21, lookback: int = 252) -> pd.Series:
    if prices.empty or len(prices) < lookback + skip:
        return _empty_weights_like(prices)
    long_term = prices.pct_change(periods=lookback)
    shifted_long = long_term.shift(skip)
    short_term = prices.pct_change(periods=skip).shift(skip)
    signal = ((shifted_long > 0) & (short_term > 0)).astype(float)
    return signal
```

Grid:

```python
    "momentum_12_1": (
        {},
        {"lookback": 126, "skip": 21},
        {"lookback": 189, "skip": 21},
    ),
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/engineer/test_momentum.py tests/protocol/test_search.py tests/protocol/test_dsl.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/engineer/momentum.py src/alphaloop/protocol/search.py tests/engineer/test_momentum.py tests/protocol/test_search.py
git commit -m "feat(search): 6/9/12-month formation lookbacks for 12-1 momentum"
```

---

### Task 4: Integration — costs flow into DSR

**Files:**
- Modify: `tests/protocol/test_gate_adapters.py`

**Interfaces:**
- Consumes: `run_hard_gates`, `MarketProfile` / `get_profile`, flipping weights
- Produces: assertion that expensive profile lowers `observed_sharpe`

- [ ] **Step 1: Write the test**

```python
def test_high_turnover_costs_reduce_dsr_observed_sharpe():
    prices = _prices(80)
    flip = pd.Series([float(i % 2) for i in range(len(prices))], index=prices.index)
    gross = compute_strategy_returns(prices, flip, cost_bps=0.0)
    net = compute_strategy_returns(prices, flip, cost_bps=1000.0)
    cheap = run_hard_gates(
        (HardGateName.DSR,),
        prices=prices,
        strategy_returns=gross,
        buy_hold_prices=prices,
        benchmark_prices=prices,
        secondary_frames=None,
        n_trials=1,
        profile=get_profile("us-equity-daily"),
        seed=1,
        strategy_fn=lambda s: flip.reindex(s.index).fillna(0.0),
    )
    from dataclasses import replace
    from alphaloop.protocol.profiles.us_equity_daily import US_EQUITY_DAILY

    expensive_profile = replace(US_EQUITY_DAILY, cost_bps=1000.0)
    expensive = run_hard_gates(
        (HardGateName.DSR,),
        prices=prices,
        strategy_returns=net,
        buy_hold_prices=prices,
        benchmark_prices=prices,
        secondary_frames=None,
        n_trials=1,
        profile=expensive_profile,
        seed=1,
        strategy_fn=lambda s: flip.reindex(s.index).fillna(0.0),
    )
    assert cheap.results[0].detail["observed_sharpe"] > expensive.results[0].detail["observed_sharpe"]
    assert expensive.results[0].detail["cost_bps"] == 1000.0
```

Import `compute_strategy_returns` at top of the test module.

- [ ] **Step 2: Run it**

Run: `python3 -m pytest tests/protocol/test_gate_adapters.py::test_high_turnover_costs_reduce_dsr_observed_sharpe -v`

Expected: PASS after Task 1–2 (detail `cost_bps` from Task 2).

- [ ] **Step 3: Commit**

```bash
git add tests/protocol/test_gate_adapters.py
git commit -m "test(protocol): DSR observed Sharpe falls after turnover costs"
```

---

### Task 5: Docs nav + full unit/integration/e2e

**Files:**
- Modify: `mkdocs.yml` (nav entries)
- Test only otherwise

- [ ] **Step 1: Add nav**

Under Requirements: `Net-of-cost validation: requirements/2026-08-19-net-of-cost-validation.md`

Under Plans: `Net-of-cost validation plan: plans/2026-08-19-net-of-cost-validation.md`

- [ ] **Step 2: Unit + integration**

Run: `python3 -m pytest -m "not e2e and not llm" -q`

Expected: PASS (existing FastAPI skips allowed).

- [ ] **Step 3: E2E**

Run: `python3 -m pytest tests/e2e -m e2e -q`

Expected: existing matrix still green; skip FOUND-after-cancel if unsealed.

- [ ] **Step 4: Commit docs if not already committed with the spec**

```bash
git add mkdocs.yml docs/requirements/2026-08-19-net-of-cost-validation.md docs/plans/2026-08-19-net-of-cost-validation.md
git commit -m "docs: net-of-cost validation and JT formation search"
```

---

## Spec coverage

| Requirement | Task |
| --- | --- |
| R1 net-of-cost returns | Task 1 |
| R2 embargoed walk-forward + adapter | Task 2 |
| R3 momentum lookback grid | Task 3 |
| R4 tests | Tasks 1–5 |

## Placeholder scan

No TBD. Callers of `compute_strategy_returns`: `protocol/loop.py`, `diagnostic/cv.py`. Callers of `walk_forward_cv`: `protocol/gates.py`, `cli/report.py`, `examples/diagnostic_demo.py` (defaults keep old embargo=0 / cost=0).
