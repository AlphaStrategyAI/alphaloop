# Pairs spread universe hedge and formation windows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Score `pairs_spread` overnight from a two-name universe without `hedge_asset`, and search 6-month / 12-month z-score windows.

**Architecture:** Resolve missing hedge in `target_weights` from `doc.universe`. Add three dicts to `method_parameter_grid`. Factor defaults unchanged.

**Tech Stack:** Existing protocol/engineer modules, pytest, Playwright real-daemon e2e.

**Spec:** `docs/requirements/2026-08-20-pairs-formation-windows.md`

## Global Constraints

- Do not promise alpha. Do not invent `FOUND`.
- Do not put `hedge_asset` on the grid.
- `{}` stays window 60. Plans live under `docs/plans/`.

---

### Task 1: Default hedge + grid

**Files:**
- Modify: `src/alphaloop/protocol/dsl.py`
- Modify: `src/alphaloop/protocol/search.py`
- Modify: `tests/protocol/test_dsl.py`
- Modify: `tests/protocol/test_search.py`
- Modify: `tests/engineer/test_mean_reversion.py`
- Modify: `tests/protocol/test_protocol_loop.py`
- Modify: `tests/runtime/test_overnight_e2e.py`
- Modify: `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Failing tests** (see spec R1–R2 and acceptance).

- [ ] **Step 2: Implement**

In `target_weights`, before `_call_factor`:

```python
        params = dict(doc.parameters)
        if doc.kind == "pairs_spread" and not params.get("hedge_asset"):
            others = [name for name in doc.universe if name != asset]
            if others:
                params["hedge_asset"] = others[0]
        weights = _call_factor(doc.kind, series, prices, params)
```

Grid:

```python
    "pairs_spread": (
        {},
        {"window": 126},
        {"window": 252},
    ),
```

- [ ] **Step 3:** `python3 -m pytest -m "not e2e and not llm" -q` then e2e.

- [ ] **Step 4: Commit**
