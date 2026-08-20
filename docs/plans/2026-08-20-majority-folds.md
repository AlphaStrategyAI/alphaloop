# Walk-forward majority of positive folds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fail walk-forward when three or more folds exist and a strict majority of fold OOS Sharpes are not above the threshold, even if the mean and median are.

**Architecture:** Add `majority_fold_ok` on the existing fold-Sharpe vector. Fold it into `WalkForwardResult.passes`. Copy `n_positive_folds` and `majority_stable` through gate `_detail` and morning `MORNING_DETAIL_KEYS`.

**Tech Stack:** Existing diagnostic/protocol modules, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-majority-folds.md`

## Global Constraints

- Do not promise alpha. Do not invent `FOUND`. No new hard gate.
- Mean, chronological halves, and median stay. Plans live under `docs/plans/`.
- `HOST_CONSTRAINT` and help sentences stay locked. No `FakeWorker` in morning e2e.

---

### Task 1: Majority helper + `WalkForwardResult.passes`

**Files:**
- Modify: `src/alphaloop/diagnostic/cv.py`
- Test: `tests/diagnostic/test_cv.py`

**Interfaces:**
- Consumes: fold OOS Sharpe vector already built in `walk_forward_cv`
- Produces: `majority_fold_ok(oos_sharpes, min_oos_sharpe) -> tuple[int, bool]`; `WalkForwardResult.n_positive_folds: int`; `WalkForwardResult.majority_stable: bool`

- [ ] **Step 1: Write the failing tests**

Add to `tests/diagnostic/test_cv.py`:

```python
from alphaloop.diagnostic.cv import majority_fold_ok


def test_majority_fold_ok_even_split_is_not_majority():
    n_positive, ok = majority_fold_ok([-1.0, -0.5, 0.6, 2.0], 0.0)
    assert n_positive == 2
    assert ok is False


def test_majority_fold_ok_skipped_when_fewer_than_three_folds():
    n_positive, ok = majority_fold_ok([-1.0, 2.0], 0.0)
    assert n_positive == 1
    assert ok is True


def test_majority_fold_ok_three_folds_need_two_positive():
    n_positive, ok = majority_fold_ok([-0.1, 0.2, 0.3], 0.0)
    assert n_positive == 2
    assert ok is True


def test_walk_forward_fails_when_only_half_of_even_folds_are_positive():
    n = 400
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    rng = np.random.default_rng(4)
    rets = np.concatenate(
        [
            rng.normal(0.0002, 0.002, 200),
            rng.normal(0.008, 0.002, 50),
            rng.normal(-0.002, 0.002, 50),
            rng.normal(0.004, 0.002, 50),
            rng.normal(-0.002, 0.002, 50),
        ]
    )
    prices = pd.Series(100.0 * np.exp(np.cumsum(rets)), index=idx)
    result = walk_forward_cv(
        prices, _buy_and_hold, train_size=200, test_size=50, step_size=50
    )
    assert result.n_folds == 4
    assert result.oos_sharpe_mean > 0
    assert result.oos_sharpe_median > 0
    assert result.regime_stable is True
    assert result.n_positive_folds == 2
    assert result.majority_stable is False
    assert result.passes is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/diagnostic/test_cv.py::test_majority_fold_ok_even_split_is_not_majority tests/diagnostic/test_cv.py::test_walk_forward_fails_when_only_half_of_even_folds_are_positive -v`

Expected: FAIL (import error or `passes is True` / missing attributes).

- [ ] **Step 3: Write minimal implementation**

In `src/alphaloop/diagnostic/cv.py`:

```python
def majority_fold_ok(
    oos_sharpes: Sequence[float] | np.ndarray,
    min_oos_sharpe: float,
) -> tuple[int, bool]:
    """Count folds strictly above *min_oos_sharpe*; majority only if n >= 3."""
    values = np.asarray(oos_sharpes, dtype=float)
    n = int(values.size)
    n_positive = int(np.sum(np.isfinite(values) & (values > min_oos_sharpe)))
    if n < 3:
        return n_positive, True
    return n_positive, n_positive * 2 > n
```

Add fields on `WalkForwardResult` (defaults at the end):

```python
    n_positive_folds: int = 0
    majority_stable: bool = True
```

In `walk_forward_cv`, after computing `oos_sharpes` / median:

```python
    n_positive_folds, majority_ok = majority_fold_ok(oos_sharpes, min_oos_sharpe)
    ...
    passes=(
        bool(oos_sharpes.mean() > min_oos_sharpe)
        and regime_stable
        and median_ok
        and majority_ok
    ),
    n_positive_folds=n_positive_folds,
    majority_stable=majority_ok,
```

Empty-fold return keeps `n_positive_folds=0`, `majority_stable=True`.

Update the `passes` comment and `summary()` to include majority.

Need `Sequence` in the `cv.py` typing imports if not already present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/diagnostic/test_cv.py -q`

Expected: PASS.

- [ ] **Step 5: Commit** (batched with Task 2 if the same cycle).

---

### Task 2: Gate detail + morning keys + overnight/e2e

**Files:**
- Modify: `src/alphaloop/protocol/gates.py`
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Test: `tests/protocol/test_gate_adapters.py`
- Test: `tests/runtime/test_overnight_e2e.py`
- Test: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: `WalkForwardResult.n_positive_folds`, `.majority_stable`
- Produces: those keys on walk_forward `detail` and morning evidence lines

- [ ] **Step 1: Write the failing assertions**

In `test_walk_forward_detail_includes_regime_fields`:

```python
    assert isinstance(detail["n_positive_folds"], int)
    assert detail["n_positive_folds"] >= 0
    assert isinstance(detail["majority_stable"], bool)
```

In `test_macd_walk_forward_records_regime_stable` (overnight) and
`test_macd_walk_forward_job_records_regime_stable` (e2e):

```python
    assert "n_positive_folds" in detail
    assert "majority_stable" in detail
```

- [ ] **Step 2: Run one adapter test to verify it fails**

Run: `python3 -m pytest tests/protocol/test_gate_adapters.py::test_walk_forward_detail_includes_regime_fields -q`

Expected: FAIL on missing keys until `_detail` copies them.

- [ ] **Step 3: Implement**

Add `"n_positive_folds"` and `"majority_stable"` to `_detail` names in
`src/alphaloop/protocol/gates.py` and to `MORNING_DETAIL_KEYS` in
`src/alphaloop/runtime/artifacts_io.py` (after `n_folds`).

- [ ] **Step 4:** unit/integration then e2e.

```bash
python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration -q
python3 -m pytest tests/e2e -m e2e -q
```

- [ ] **Step 5: Commit**

---

### Task 3: Docs nav + median-fold loop-exit pointer

**Files:**
- Modify: `mkdocs.yml`
- Modify: `docs/requirements/2026-08-20-median-fold-sharpe.md`

- [ ] Add nav entries next to Median fold Sharpe.
- [ ] Point median-fold §4/§6 at this cycle (majority is no longer remaining).
- [ ] Commit with the feature if not already included.
