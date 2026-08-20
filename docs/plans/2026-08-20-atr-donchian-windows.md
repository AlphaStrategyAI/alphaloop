# ATR breakout Donchian / Turtle lookbacks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Search `atr_breakout` on Turtle Donchian entries 20 and 55, keeping `{}` as the in-repo 50-day default.

**Architecture:** Three dicts in `method_parameter_grid`. Factor and close-only adapter unchanged.

**Tech Stack:** Existing protocol/engineer modules, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-atr-donchian-windows.md`

## Global Constraints

- Do not promise alpha. Do not invent `FOUND`.
- Do not grid `atr_window` or `atr_multiplier`.
- Plans live under `docs/plans/`.

---

### Task 1: Grid + tests

**Files:** `src/alphaloop/protocol/search.py`, `tests/protocol/test_search.py`, `tests/engineer/test_volatility_volume.py`, `tests/protocol/test_protocol_loop.py`, `tests/runtime/test_overnight_e2e.py`, `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Tests** matching spec acceptance (grid, signal change 20 vs 55, protocol 3 incomplete-then-pass, overnight/e2e ledger kind).

- [ ] **Step 2: Implement**

```python
    "atr_breakout": (
        {},
        {"breakout_window": 20},
        {"breakout_window": 55},
    ),
```

- [ ] **Step 3:** unit/integration then e2e.

- [ ] **Step 4: Commit**
