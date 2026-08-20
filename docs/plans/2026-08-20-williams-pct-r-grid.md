# Williams %R overnight adapter and literature grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Score Williams %R overnight on close-only prices, expose `period`, and search the −80 oversold rule plus Williams’ 10-day lookback.

**Architecture:** Reuse the ATR close-only OHLC wrapper. Add `period` to `ohlr_4_pct`. Put three dicts in `method_parameter_grid`.

**Tech Stack:** Existing engineer/protocol modules, pytest, Playwright real-daemon e2e.

**Spec:** `docs/requirements/2026-08-20-williams-pct-r-grid.md`

## Global Constraints

- Do not promise alpha. Do not invent `FOUND`.
- Do not rename `ohlr_4_pct`. Do not change `{}` defaults (14, threshold 0).
- Other method grids stay unchanged.
- Plans live under `docs/plans/`.

---

### Task 1: `period` on `ohlr_4_pct`

**Files:**
- Modify: `src/alphaloop/engineer/mean_reversion.py`
- Modify: `tests/engineer/test_mean_reversion.py`

**Interfaces:**
- Produces: `ohlr_4_pct(ohlc, period: int = 14, threshold: float = 0.0) -> pd.Series`

- [ ] **Step 1: Write failing tests**

```python
def test_ohlr_period_changes_warmup():
    idx = pd.date_range("2020-01-01", periods=40, freq="B")
    p = pd.Series(np.linspace(200, 100, 40), index=idx)
    ohlc = _make_ohlc(p)
    fast = ohlr_4_pct(ohlc, period=10, threshold=80.0)
    slow = ohlr_4_pct(ohlc, period=21, threshold=80.0)
    assert float(fast.iloc[12]) >= 0.0
    assert float(slow.iloc[12]) == 0.0


def test_ohlr_oversold_threshold_longs_downtrend():
    idx = pd.date_range("2020-01-01", periods=200, freq="B")
    p = pd.Series(np.linspace(200, 100, 200), index=idx)
    w = ohlr_4_pct(_make_ohlc(p), period=14, threshold=80.0)
    assert w.iloc[20:].sum() > 100
```

- [ ] **Step 2: Run to fail**

Run: `python3 -m pytest tests/engineer/test_mean_reversion.py::test_ohlr_period_changes_warmup -v`

Expected: FAIL — unexpected keyword `period`.

- [ ] **Step 3: Implement**

```python
def ohlr_4_pct(
    ohlc: pd.DataFrame,
    threshold: float = 0.0,
    period: int = 14,
) -> pd.Series:
    if ohlc.empty or len(ohlc) < period:
        return pd.Series(0.0, index=ohlc.index, dtype=float)
    ...
    hh = high.rolling(period).max()
    ll = low.rolling(period).min()
```

Keep the existing `threshold` signal rule.

- [ ] **Step 4: Run** `python3 -m pytest tests/engineer/test_mean_reversion.py -v` — PASS

- [ ] **Step 5: Commit** `feat(engineer): expose Williams %R lookback period`

---

### Task 2: Close-only adapter + grid

**Files:**
- Modify: `src/alphaloop/protocol/dsl.py`
- Modify: `src/alphaloop/protocol/search.py`
- Modify: `tests/protocol/test_dsl.py`
- Modify: `tests/protocol/test_search.py`
- Modify: `tests/protocol/test_protocol_loop.py`
- Modify: `tests/runtime/test_overnight_e2e.py`
- Modify: `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Failing tests**

```python
def test_ohlr_close_only_target_weights_do_not_raise():
    doc = parse_strategy_document(_payload(kind="ohlr_4_pct", universe=["AAPL"]))
    prices = _rising_prices(40)
    weights = target_weights(doc, {"AAPL": prices}, prices.index[-1])
    assert weights["AAPL"] >= 0.0


def test_ohlr_grid_is_williams_oversold_variants():
    grid = method_parameter_grid("ohlr_4_pct")
    assert grid[0] == {}
    assert {"threshold": 80.0} in grid
    assert {"period": 10, "threshold": 80.0} in grid
    assert len(grid) == 3
    frozen = _hypothesis()
    for params in grid:
        assert classify_revision(frozen, ("dsr",), params) is RevisionKind.METHOD
```

Copy `test_bollinger_protocol_walks_three_method_trials` with `signal_mechanism="ohlr_4_pct"`.

Overnight + e2e: same pattern as Bollinger, `kind == "ohlr_4_pct"`. Do not assert `FOUND`.

- [ ] **Step 2: Run to fail** — adapter KeyError / grid `({})`.

- [ ] **Step 3: Implement**

In `_call_factor`:

```python
    if kind in {"atr_breakout", "ohlr_4_pct"}:
        ohlc = pd.DataFrame({"high": primary, "low": primary, "close": primary})
        return fn(ohlc, **kwargs)
```

Grid:

```python
    "ohlr_4_pct": (
        {},
        {"threshold": 80.0},
        {"period": 10, "threshold": 80.0},
    ),
```

- [ ] **Step 4:** `python3 -m pytest -m "not e2e and not llm" -q` then `python3 -m pytest tests/e2e -m e2e -q`

- [ ] **Step 5: Commit**
