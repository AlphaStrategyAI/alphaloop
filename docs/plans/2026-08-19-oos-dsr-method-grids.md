# Out-of-sample DSR and literature method grids Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When walk-forward is a required hard gate, run DSR and benchmark gates on concatenated OOS net returns; give overnight vs-random enough bootstrap power; search RSI/ROC on Wilder and formation windows.

**Architecture:** `walk_forward_cv` exposes `oos_returns`. `run_hard_gates` precomputes walk-forward once if required, then points DSR/vs_* at that series (or full-sample if walk-forward is not required). Short OOS (<30) omits DSR. Search grids are data in `method_parameter_grid`.

**Tech Stack:** Existing pandas diagnostic/protocol modules, pytest, Playwright e2e against a real daemon.

**Spec:** `docs/requirements/2026-08-19-oos-dsr-method-grids.md`

## Global Constraints

- Do not promise alpha. Missing gates → `INCONCLUSIVE`, never fake `FOUND`.
- Net-of-cost + embargoed walk-forward from the previous cycle stay.
- `MIN_DSR_OBSERVATIONS = 30`. Overnight `vs_random`: `n_simulations=200`, `block_size=21`.
- `returns_scope` is `"oos_walk_forward"` or `"full_sample"`.
- Morning e2e: real daemon + Chromium; no `FakeWorker`; do not invent `FOUND`.
- Plans live under `docs/plans/`.

---

### Task 1: `WalkForwardResult.oos_returns`

**Files:**
- Modify: `src/alphaloop/diagnostic/cv.py`
- Modify: `tests/diagnostic/test_cv.py`

**Interfaces:**
- Produces: `WalkForwardResult.oos_returns: pd.Series`

- [ ] **Step 1: Write the failing test**

```python
def test_walk_forward_exposes_concatenated_oos_returns():
    prices = _make_prices(400)
    result = walk_forward_cv(
        prices, _buy_and_hold, train_size=200, test_size=50, embargo_size=0, step_size=50
    )
    assert result.n_folds >= 1
    assert len(result.oos_returns) == result.n_folds * 50
    assert list(result.oos_returns.index[:50]) == list(
        prices.index[200:250]
    )
```

- [ ] **Step 2: Run to fail**

Run: `python3 -m pytest tests/diagnostic/test_cv.py::test_walk_forward_exposes_concatenated_oos_returns -v`

Expected: FAIL — no `oos_returns`.

- [ ] **Step 3: Implement**

Add field to `WalkForwardResult`:

```python
    oos_returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
```

In the fold loop, collect `test_returns` in a list. After the loop:

```python
    concat = (
        pd.concat(oos_parts)
        if oos_parts
        else pd.Series(dtype=float)
    )
    concat = concat[~concat.index.duplicated(keep="first")]
```

Pass `oos_returns=concat` into both return paths (empty folds → empty series).

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/diagnostic/test_cv.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/diagnostic/cv.py tests/diagnostic/test_cv.py
git commit -m "feat(diagnostic): expose concatenated walk-forward OOS returns"
```

---

### Task 2: Score OOS when walk-forward is required

**Files:**
- Modify: `src/alphaloop/protocol/gates.py`
- Modify: `tests/protocol/test_gate_adapters.py`

**Interfaces:**
- Consumes: `WalkForwardResult.oos_returns`
- Produces: DSR/vs_* use OOS series + `returns_scope` in `detail`

Constants in `gates.py`:

```python
MIN_DSR_OBSERVATIONS = 30
VS_RANDOM_SIMULATIONS = 200
VS_RANDOM_BLOCK = 21
```

`run_hard_gates` outline:

```python
    wf_result = None
    if HardGateName.WALK_FORWARD in required:
        try:
            train, test, embargo = _walk_forward_windows(len(prices), profile.periods_per_year)
            wf_result = walk_forward_cv(
                prices, strategy_fn,
                train_size=train, test_size=test, embargo_size=embargo,
                cost_bps=profile.cost_bps, periods_per_year=profile.periods_per_year,
            )
        except Exception:
            wf_result = None
    oos = (
        wf_result.oos_returns
        if wf_result is not None and wf_result.oos_returns is not None
        else None
    )
    use_oos = (
        HardGateName.WALK_FORWARD in required
        and oos is not None
        and len(oos) > 0
    )
    scored = oos if use_oos else strategy_returns
    scope = "oos_walk_forward" if use_oos else "full_sample"
```

For DSR: if `len(scored) < MIN_DSR_OBSERVATIONS`, `continue` (omit row).

For WALK_FORWARD: if `wf_result is None`, `continue`; else build `GateResult` from `wf_result` without calling `walk_forward_cv` again.

vs_random: `n_simulations=VS_RANDOM_SIMULATIONS`, `block_size=VS_RANDOM_BLOCK`, `strategy_returns=scored`.

After each successful row, `detail` gets `cost_bps` (existing) and `returns_scope` for DSR/vs_* / walk_forward (walk_forward scope is always oos).

- [ ] **Step 1: Write failing tests**

```python
def test_dsr_uses_oos_returns_when_walk_forward_required():
    prices = _prices(80)
    oos = pd.Series(
        [0.001] * 40, index=pd.bdate_range("2020-06-01", periods=40), dtype=float
    )
    with mock.patch("alphaloop.protocol.gates.deflated_sharpe") as dsr, mock.patch(
        "alphaloop.protocol.gates.walk_forward_cv"
    ) as wf:
        wf.return_value = mock.Mock(
            passes=True, oos_sharpe_mean=0.1, oos_returns=oos, n_folds=1
        )
        dsr.return_value = mock.Mock(
            passes=True, dsr=0.99, observed_sharpe=1.0, p_value=0.01
        )
        evidence = run_hard_gates(
            (HardGateName.DSR, HardGateName.WALK_FORWARD),
            prices=prices,
            strategy_returns=_returns(prices),
            buy_hold_prices=prices,
            benchmark_prices=prices,
            secondary_frames=None,
            n_trials=2,
            profile=get_profile("us-equity-daily"),
            seed=1,
            strategy_fn=_strategy_fn,
        )
        dsr.assert_called_once()
        passed = dsr.call_args.kwargs.get("returns")
        if passed is None:
            passed = dsr.call_args.args[2] if len(dsr.call_args.args) > 2 else None
        assert list(passed) == list(oos)
        by_name = {row.name: row for row in evidence.results}
        assert by_name[HardGateName.DSR].detail["returns_scope"] == "oos_walk_forward"


def test_dsr_omitted_when_oos_shorter_than_30():
    prices = _prices(80)
    oos = pd.Series([0.001] * 10, index=pd.bdate_range("2020-06-01", periods=10))
    with mock.patch("alphaloop.protocol.gates.deflated_sharpe") as dsr, mock.patch(
        "alphaloop.protocol.gates.walk_forward_cv"
    ) as wf:
        wf.return_value = mock.Mock(
            passes=True, oos_sharpe_mean=0.1, oos_returns=oos, n_folds=1
        )
        with pytest.raises(Exception):
            run_hard_gates(
                (HardGateName.DSR, HardGateName.WALK_FORWARD),
                ...
            )
```

`evaluate_hard_gates` raises `IncompleteEvidenceError` if DSR missing. Catch that:

```python
        with pytest.raises(IncompleteEvidenceError):
            run_hard_gates(...)
        dsr.assert_not_called()
```

Import `IncompleteEvidenceError`.

```python
def test_dsr_only_stays_full_sample():
    prices = _prices()
    evidence = run_hard_gates((HardGateName.DSR,), ...)
    assert evidence.results[0].detail["returns_scope"] == "full_sample"


def test_vs_random_adapter_uses_powered_bootstrap():
    prices = _prices(80)
    with mock.patch("alphaloop.protocol.gates.vs_random") as vr:
        vr.return_value = mock.Mock(passes=True, p_value=0.1, strategy_sharpe=0.5)
        run_hard_gates((HardGateName.VS_RANDOM,), ...)
        assert vr.call_args.kwargs["n_simulations"] == 200
        assert vr.call_args.kwargs["block_size"] == 21
```

- [ ] **Step 2: Run to fail**

Run: `python3 -m pytest tests/protocol/test_gate_adapters.py::test_dsr_uses_oos_returns_when_walk_forward_required tests/protocol/test_gate_adapters.py::test_vs_random_adapter_uses_powered_bootstrap -v`

Expected: FAIL.

- [ ] **Step 3: Implement `run_hard_gates` / `_run_one`**

Refactor `_run_one` to accept `scored_returns`, `wf_result`, `returns_scope`. Do not call `walk_forward_cv` inside `_run_one` for WALK_FORWARD; use `wf_result`.

- [ ] **Step 4: Run**

Run: `python3 -m pytest tests/protocol/test_gate_adapters.py tests/protocol/test_protocol_loop.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/protocol/gates.py tests/protocol/test_gate_adapters.py
git commit -m "feat(gates): apply DSR and benchmarks to walk-forward OOS returns"
```

---

### Task 3: RSI / ROC literature grids

**Files:**
- Modify: `src/alphaloop/protocol/search.py`
- Modify: `tests/protocol/test_search.py`

- [ ] **Step 1: Tests**

```python
def test_rsi_grid_is_wilder_variants():
    grid = method_parameter_grid("rsi")
    assert grid[0] == {}
    assert {"window": 9} in grid
    assert {"window": 21} in grid
    assert len(grid) == 3


def test_roc_grid_is_formation_windows():
    grid = method_parameter_grid("roc")
    assert grid[0] == {}
    assert {"window": 63} in grid
    assert {"window": 126} in grid
    assert len(grid) == 3
```

- [ ] **Step 2: Run to fail**

Run: `python3 -m pytest tests/protocol/test_search.py -v`

Expected: FAIL on new tests.

- [ ] **Step 3: Set grids**

```python
    "rsi": ({}, {"window": 9}, {"window": 21}),
    "roc": ({}, {"window": 63}, {"window": 126}),
```

- [ ] **Step 4–5: Pass and commit**

```bash
git commit -m "feat(search): Wilder RSI 9/21 and ROC 63/126 method grids"
```

---

### Task 4: Docs nav + full verification

**Files:**
- Modify: `mkdocs.yml`

- [ ] Add Requirements + Plans nav entries for the spec and this plan.

- [ ] `python3 -m pytest -m "not e2e and not llm" -q`

- [ ] `python3 -m pytest tests/e2e -m e2e -q`

- [ ] Commit docs with the spec/plan if not already committed.

---

## Spec coverage

| Requirement | Task |
| --- | --- |
| R1 oos_returns | Task 1 |
| R2 OOS scoring | Task 2 |
| R3 30-obs DSR floor | Task 2 |
| R4 vs_random power | Task 2 |
| R5 RSI/ROC grids | Task 3 |
| Tests + e2e | Task 4 |

## Placeholder scan

No TBD. `walk_forward_cv` is called at most once per `run_hard_gates`.
