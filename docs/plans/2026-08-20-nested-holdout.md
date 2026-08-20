# Nested Final Holdout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock a final holdout suffix so WF, CPCV, DSR, vs_*, and PBO cannot select on the most recent returns.

**Architecture:** `nested_holdout_bounds` in `alphaloop.diagnostic.holdout`. `run_hard_gates` scores selection gates on the inner prefix and ANDs holdout Sharpe into DSR/WF. `run_protocol` truncates PBO inputs to `inner_end`.

**Tech Stack:** pandas, existing `compute_strategy_returns`, pytest, Playwright.

## Global Constraints

- Local-first overnight lab. Do not promise alpha. Do not invent `FOUND`.
- No new `HardGateName`. No FakeWorker in morning e2e.
- `alphaloop.protocol` must not import `runtime`.
- Use `python3`.

---

### Task 1: Bounds + gate split

**Files:**
- Create: `src/alphaloop/diagnostic/holdout.py`
- Modify: `src/alphaloop/protocol/gates.py`, `src/alphaloop/runtime/artifacts_io.py`
- Test: `tests/diagnostic/test_holdout.py`, `tests/protocol/test_gate_adapters.py`

- [ ] Failing tests for bounds None vs `(inner, start, n)`, 400-bar `holdout_passes is True`, late-crash DSR fail, 80-bar no holdout keys.

- [ ] Implement bounds: holdout `max(30, ppY/4)`, embargo `max(1, ppY/52)`, inner >= 120.

- [ ] `run_hard_gates` slices inner for WF/CPCV/DSR/vs_*; scores holdout with `strategy_fn` on `prices.iloc[:holdout_end]`; ANDs onto DSR else WF else first row.

### Task 2: PBO inner slice + e2e

**Files:**
- Modify: `src/alphaloop/protocol/loop.py`, `tests/e2e/test_morning_console.py`, `mkdocs.yml`

- [ ] On PBO, slice each trial return series to `inner_end` when bounds exist.

- [ ] MACD e2e asserts `holdout_passes` in walk_forward detail.

- [ ] Register req/plan in `mkdocs.yml`. Unit + e2e. Commit.
