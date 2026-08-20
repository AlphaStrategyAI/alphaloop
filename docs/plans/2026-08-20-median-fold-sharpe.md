# Walk-forward median fold OOS Sharpe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fail walk-forward when three or more folds exist and the median fold OOS Sharpe is not positive, even if the mean is.

**Architecture:** `WalkForwardResult` already has `oos_sharpe_median`. Fold it into `passes`. Copy it in `_detail`.

**Tech Stack:** Existing diagnostic/protocol modules, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-median-fold-sharpe.md`

## Global Constraints

- Do not promise alpha. Do not invent `FOUND`. No new hard gate.
- Chronological halves stay. Plans live under `docs/plans/`.

---

### Task 1: Median in `passes` + detail

**Files:** `src/alphaloop/diagnostic/cv.py`, `src/alphaloop/protocol/gates.py`, `tests/diagnostic/test_cv.py`, `tests/protocol/test_gate_adapters.py`, `tests/runtime/test_overnight_e2e.py`, `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Test** three-fold up/down/up path: mean > 0, halves > 0, median < 0, `passes` False. Two-fold path does not require median. Detail includes `oos_sharpe_median`. Overnight/e2e walk_forward detail has the key.

- [ ] **Step 2: Implement**

```python
    median_ok = (
        True
        if len(folds) < 3
        else bool(float(np.median(oos_sharpes)) > min_oos_sharpe)
    )
    passes=bool(oos_sharpes.mean() > min_oos_sharpe) and regime_stable and median_ok,
```

Add `"oos_sharpe_median"` to `_detail` names.

- [ ] **Step 3:** unit/integration then e2e.

- [ ] **Step 4: Commit**
