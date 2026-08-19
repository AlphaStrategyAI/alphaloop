# Chronological regime stability and Appel MACD grids Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fail walk-forward when concatenated OOS returns are long enough to split in half and either chronological half has non-positive Sharpe; search MACD on Appel’s original daily settings plus the street default.

**Architecture:** A helper splits the OOS series at the midpoint. `walk_forward_cv` folds that check into `WalkForwardResult.passes` and exposes the half Sharpes. Gate `detail` copies those fields. MACD grid is data in `method_parameter_grid`. No new `HardGateName`.

**Tech Stack:** Existing pandas diagnostic/protocol modules, pytest, Playwright e2e against a real daemon.

**Spec:** `docs/requirements/2026-08-19-regime-stability-macd-grid.md`

## Global Constraints

- Do not promise alpha. Missing gates → `INCONCLUSIVE`, never fake `FOUND`.
- OOS DSR, net-of-cost, and embargoed walk-forward from previous cycles stay.
- `MIN_REGIME_OBSERVATIONS = 30`. Short OOS does not fail as unstable.
- Do not add a seventh hard gate. Failed halves are failed `walk_forward`.
- Morning e2e: real daemon + Chromium; no `FakeWorker`; do not invent `FOUND`.
- Plans live under `docs/plans/`. Python 3.9: `Optional`, not `|`.

---

### Task 1: Chronological half-Sharpe helper

**Files:**
- Modify: `src/alphaloop/diagnostic/cv.py`
- Modify: `tests/diagnostic/test_cv.py`

**Interfaces:**
- Produces: `chronological_half_sharpes(returns: pd.Series, periods_per_year: int = 252) -> tuple[float, float, bool]`
- Produces: `MIN_REGIME_OBSERVATIONS = 30`

- [ ] **Step 1: Write the failing tests**

Add to `tests/diagnostic/test_cv.py`:

```python
from alphaloop.diagnostic.cv import (  # noqa: E402
    WalkForwardFold,
    WalkForwardResult,
    chronological_half_sharpes,
    walk_forward_cv,
)


def test_chronological_half_sharpes_both_positive():
    rng = np.random.default_rng(0)
    rets = pd.Series(
        np.concatenate(
            [rng.normal(0.01, 0.002, 20), rng.normal(0.01, 0.002, 20)]
        )
    )
    first, second, evaluated = chronological_half_sharpes(rets)
    assert evaluated is True
    assert first > 0
    assert second > 0


def test_chronological_half_sharpes_second_half_negative():
    rng = np.random.default_rng(0)
    rets = pd.Series(
        np.concatenate(
            [rng.normal(0.01, 0.002, 20), rng.normal(-0.01, 0.002, 20)]
        )
    )
    first, second, evaluated = chronological_half_sharpes(rets)
    assert evaluated is True
    assert first > 0
    assert second < 0


def test_chronological_half_sharpes_short_not_evaluated():
    first, second, evaluated = chronological_half_sharpes(pd.Series([0.01] * 20))
    assert evaluated is False
    assert first == 0.0
    assert second == 0.0
```

- [ ] **Step 2: Run to fail**

Run: `python3 -m pytest tests/diagnostic/test_cv.py::test_chronological_half_sharpes_both_positive tests/diagnostic/test_cv.py::test_chronological_half_sharpes_second_half_negative tests/diagnostic/test_cv.py::test_chronological_half_sharpes_short_not_evaluated -v`

Expected: FAIL — `chronological_half_sharpes` is not defined.

- [ ] **Step 3: Implement the helper**

In `src/alphaloop/diagnostic/cv.py`, after `_annualized_sharpe`:

```python
MIN_REGIME_OBSERVATIONS = 30


def chronological_half_sharpes(
    returns: pd.Series,
    periods_per_year: int = 252,
) -> tuple[float, float, bool]:
    """Split *returns* at the midpoint and Sharpe each half.

    Returns ``(first_half_sharpe, second_half_sharpe, evaluated)``.
    ``evaluated`` is False when ``len(returns) < MIN_REGIME_OBSERVATIONS``.
    """
    if returns is None or len(returns) < MIN_REGIME_OBSERVATIONS:
        return 0.0, 0.0, False
    mid = len(returns) // 2
    first = _annualized_sharpe(returns.iloc[:mid], periods_per_year)
    second = _annualized_sharpe(returns.iloc[mid:], periods_per_year)
    return first, second, True
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/diagnostic/test_cv.py::test_chronological_half_sharpes_both_positive tests/diagnostic/test_cv.py::test_chronological_half_sharpes_second_half_negative tests/diagnostic/test_cv.py::test_chronological_half_sharpes_short_not_evaluated -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/diagnostic/cv.py tests/diagnostic/test_cv.py
git commit -m "feat(diagnostic): split OOS returns into chronological half Sharpes"
```

---

### Task 2: Fold regime stability into walk-forward `passes`

**Files:**
- Modify: `src/alphaloop/diagnostic/cv.py`
- Modify: `tests/diagnostic/test_cv.py`

**Interfaces:**
- Consumes: `chronological_half_sharpes`
- Produces: `WalkForwardResult.first_half_sharpe`, `.second_half_sharpe`, `.regime_stable`
- Produces: `passes` is mean-fold Sharpe **and** `regime_stable` when evaluated

- [ ] **Step 1: Write the failing tests**

```python
def test_walk_forward_fails_when_second_oos_half_is_negative():
    n = 400
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    rng = np.random.default_rng(1)
    rets = np.concatenate(
        [rng.normal(0.004, 0.002, 300), rng.normal(-0.004, 0.002, 100)]
    )
    prices = pd.Series(100.0 * np.exp(np.cumsum(rets)), index=idx)
    result = walk_forward_cv(
        prices, _buy_and_hold, train_size=200, test_size=50, step_size=50
    )
    assert len(result.oos_returns) >= 30
    assert result.oos_sharpe_mean > 0
    assert result.first_half_sharpe > 0
    assert result.second_half_sharpe < 0
    assert result.regime_stable is False
    assert result.passes is False


def test_walk_forward_does_not_fail_regime_when_oos_short():
    prices = _make_prices(50, drift=0.001)
    result = walk_forward_cv(
        prices, _buy_and_hold, train_size=20, test_size=8, step_size=8
    )
    assert len(result.oos_returns) < 30
    assert result.regime_stable is True
```

Existing `test_walk_forward_buy_and_hold_is_profitable` MUST still pass.

- [ ] **Step 2: Run to fail**

Run: `python3 -m pytest tests/diagnostic/test_cv.py::test_walk_forward_fails_when_second_oos_half_is_negative tests/diagnostic/test_cv.py::test_walk_forward_does_not_fail_regime_when_oos_short tests/diagnostic/test_cv.py::test_walk_forward_buy_and_hold_is_profitable -v`

Expected: FAIL — no `regime_stable` / `passes` still True on the mixed series.

- [ ] **Step 3: Implement**

Add fields on `WalkForwardResult` (defaults at the end):

```python
    oos_returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    first_half_sharpe: float = 0.0
    second_half_sharpe: float = 0.0
    regime_stable: bool = True
```

Update `summary()` to include `regime_stable` and both half Sharpes.

After concatenating `oos_returns`, in **both** return paths:

```python
    first, second, evaluated = chronological_half_sharpes(concat, periods_per_year)
    regime_stable = (first > 0.0 and second > 0.0) if evaluated else True
```

Empty folds: `passes=False`, still set the three fields from the helper.

Non-empty:

```python
        passes=bool(oos_sharpes.mean() > min_oos_sharpe) and regime_stable,
        oos_returns=concat,
        first_half_sharpe=first,
        second_half_sharpe=second,
        regime_stable=regime_stable,
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/diagnostic/test_cv.py -v`

Expected: PASS. If the mixed-series seed does not keep `oos_sharpe_mean > 0`, change only the RNG seed or the two drift values; do not weaken the assertion.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/diagnostic/cv.py tests/diagnostic/test_cv.py
git commit -m "feat(diagnostic): fail walk-forward when an OOS half has non-positive Sharpe"
```

---

### Task 3: Copy regime fields into walk-forward gate detail

**Files:**
- Modify: `src/alphaloop/protocol/gates.py`
- Modify: `tests/protocol/test_gate_adapters.py`

**Interfaces:**
- Consumes: `WalkForwardResult.first_half_sharpe`, `.second_half_sharpe`, `.regime_stable`
- Produces: those keys on `GateResult.detail` for `WALK_FORWARD`

- [ ] **Step 1: Write the failing test**

```python
def test_walk_forward_detail_includes_regime_fields():
    prices = _prices(400)
    evidence = run_hard_gates(
        (HardGateName.WALK_FORWARD,),
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
    detail = evidence.results[0].detail
    assert "regime_stable" in detail
    assert "first_half_sharpe" in detail
    assert "second_half_sharpe" in detail
    assert isinstance(detail["regime_stable"], bool)
```

Do **not** replace `oos_returns` on mocked walk-forward tests with a Mock (no `len`). Existing mocks that pass a real `pd.Series` stay.

- [ ] **Step 2: Run to fail**

Run: `python3 -m pytest tests/protocol/test_gate_adapters.py::test_walk_forward_detail_includes_regime_fields -v`

Expected: FAIL — `regime_stable` not in `detail`.

- [ ] **Step 3: Implement**

In `_detail`, extend the name tuple:

```python
    for name in (
        "dsr",
        "passes",
        "p_value",
        "observed_sharpe",
        "oos_sharpe_mean",
        "first_half_sharpe",
        "second_half_sharpe",
        "regime_stable",
    ):
```

Keep `isinstance(value, (int, float, bool, str))` so MagicMock attributes are skipped.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/protocol/test_gate_adapters.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/protocol/gates.py tests/protocol/test_gate_adapters.py
git commit -m "feat(gates): copy walk-forward regime fields into gate detail"
```

---

### Task 4: Appel MACD method grid

**Files:**
- Modify: `src/alphaloop/protocol/search.py`
- Modify: `tests/protocol/test_search.py`
- Modify: `tests/engineer/test_momentum.py`

**Interfaces:**
- Produces: `method_parameter_grid("macd")` is exactly the three dicts in R4

- [ ] **Step 1: Write the failing tests**

In `tests/protocol/test_search.py`:

```python
def test_macd_grid_is_appel_variants():
    grid = method_parameter_grid("macd")
    assert grid[0] == {}
    assert {"fast": 8, "slow": 17, "signal_period": 9} in grid
    assert {"fast": 12, "slow": 25, "signal_period": 9} in grid
    assert len(grid) == 3
    frozen = _hypothesis()
    for params in grid:
        assert classify_revision(frozen, ("dsr",), params) is RevisionKind.METHOD
```

In `tests/engineer/test_momentum.py`:

```python
def test_macd_appel_buy_params_weights_in_01():
    p = _make_prices()
    w = macd(p, fast=8, slow=17, signal_period=9)
    assert w.between(0, 1).all()
```

- [ ] **Step 2: Run to fail**

Run: `python3 -m pytest tests/protocol/test_search.py::test_macd_grid_is_appel_variants tests/engineer/test_momentum.py::test_macd_appel_buy_params_weights_in_01 -v`

Expected: FAIL — MACD grid is `({})`.

- [ ] **Step 3: Implement**

In `src/alphaloop/protocol/search.py` add:

```python
    "macd": (
        {},
        {"fast": 8, "slow": 17, "signal_period": 9},
        {"fast": 12, "slow": 25, "signal_period": 9},
    ),
```

Do not change `macd()` defaults. Do not change RSI/ROC/momentum grids.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/protocol/test_search.py tests/engineer/test_momentum.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/protocol/search.py tests/protocol/test_search.py tests/engineer/test_momentum.py
git commit -m "feat(search): walk Appel MACD (8,17,9) and (12,25,9) as method repairs"
```

---

### Task 5: Overnight worker and morning e2e

**Files:**
- Modify: `tests/runtime/test_overnight_e2e.py`
- Modify: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: real `run_worker` (not FakeWorker for the research path) and real daemon + Chromium
- Produces: `evidence/gates.json` contains `regime_stable` for a `macd` + `walk_forward` spec

- [ ] **Step 1: Write the overnight test**

```python
import json

from alphaloop.contracts.gates import evidence_from_dict, HardGateName


def test_macd_walk_forward_records_regime_stable(tmp_path):
    frame = _prices_frame()
    parquet = tmp_path / "datasets" / "ds_macd" / "prices.parquet"
    parquet.parent.mkdir(parents=True)
    frame.to_parquet(parquet)
    digest = hash_bytes(parquet.read_bytes())
    spec = new_research_spec(
        statement="MACD crossover works in US large caps net of costs",
        economic_logic="trend continuation after EMA spread confirmation",
        signal_mechanism="macd",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("walk_forward",),
        seed=7,
        time_budget_s=30,
        cost_budget_usd=1.0,
        dataset=DatasetRef(dataset_id="ds_macd", sha256=digest),
    )
    api = _api(tmp_path)
    created = api.create_run(spec)
    run_id = created["run_id"]
    layout = RunLayout(tmp_path / run_id)
    assert run_worker(run_id, tmp_path) == 0
    gates_path = layout.evidence / "gates.json"
    assert gates_path.is_file()
    evidence = evidence_from_dict(json.loads(gates_path.read_text(encoding="utf-8")))
    by_name = {row.name: row for row in evidence.results}
    assert HardGateName.WALK_FORWARD in by_name
    assert "regime_stable" in by_name[HardGateName.WALK_FORWARD].detail
    assert isinstance(by_name[HardGateName.WALK_FORWARD].detail["regime_stable"], bool)
```

Keep using `run_worker` for the research path. `FakeWorker` on the supervisor is only for spawn accounting in the existing test; this new test may reuse `_api`.

- [ ] **Step 2: Write the Playwright test**

In `tests/e2e/test_morning_console.py`:

```python
def test_macd_walk_forward_job_records_regime_stable(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"], dataset_id="ds_macd_wf")
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    page.fill(
        "#spec-yaml",
        _spec_yaml(
            dataset,
            statement="MACD crossover works in US large caps net of costs",
            signal_mechanism="macd",
            hard_gates=["walk_forward"],
            time_budget_s=60,
        ),
    )
    page.click("#submit-job")
    outcome = _wait_list_outcome(page, timeout_ms=90000)
    assert outcome in _OUTCOMES
    run_id = _first_run_id(page)
    layout = RunLayout(real_daemon["data_dir"] / run_id)
    gates_path = layout.evidence / "gates.json"
    assert gates_path.is_file()
    payload = json.loads(gates_path.read_text(encoding="utf-8"))
    rows = {row["name"]: row for row in payload["results"]}
    assert "walk_forward" in rows
    assert "regime_stable" in rows["walk_forward"]["detail"]
    assert isinstance(rows["walk_forward"]["detail"]["regime_stable"], bool)
    assert "target found" not in page.content()
```

Do not assert `FOUND`. Default `dsr`-only specs stay unchanged.

- [ ] **Step 3: Run unit/integration first**

Run: `python3 -m pytest -m "not e2e and not llm" -q`

Expected: PASS (existing skips allowed).

- [ ] **Step 4: Run e2e**

Run: `python3 -m pytest tests/e2e -m e2e tests/runtime/test_overnight_e2e.py -q`

Expected: PASS. Skip Chromium only if the browser binary is missing; do not skip the overnight worker test.

- [ ] **Step 5: Commit**

```bash
git add tests/runtime/test_overnight_e2e.py tests/e2e/test_morning_console.py
git commit -m "test: record walk-forward regime_stable on macd overnight and morning e2e"
```

---

## Self-review

1. **Spec coverage:** R1 helper → Task 1. R2 walk-forward passes → Task 2. R2 detail copy → Task 3. R3 no new gate → no enum task. R4 MACD grid → Task 4. Acceptance e2e → Task 5.
2. **Placeholders:** none.
3. **Types:** `chronological_half_sharpes` → `(float, float, bool)`; `regime_stable: bool`; grid dicts use `fast`/`slow`/`signal_period` matching `macd()`.
