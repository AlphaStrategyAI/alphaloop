---
title: "Net-of-cost validation and economically motivated method search"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-19"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-19-five-minute-morning-review.md
---

# Net-of-cost validation and economically motivated method search

**Date:** 2026-08-19
**Status:** Approved for this implementation cycle
**Scope:** How the overnight protocol **searches** method variants and
**validates** candidates. Not a new product category. Not CPCV as a
full combinatorial expander. Not a trading cost model with impact
functions.

## 1. Why this cycle exists

The PRD (`docs/requirements/product-positioning-requirements.md`)
defines alphaloop as an overnight lab whose value is honest evidence,
not promised alpha.

- §5.4: the research engine generates candidates and runs quantitative
  diagnostics.
- §5.5: each market profile separately defines **transaction-cost
  assumptions**.
- §6.1: the loop may repair methodology (parameter coverage), not the
  frozen economic hypothesis. Each repair counts in multiple-testing.
- §6.2: **failure after transaction costs** and **failure of DSR or
  another predeclared gate** do not justify further search.
- The canonical hypothesis example is net-of-cost:
  *does 12-1 momentum produce net-of-cost, out-of-sample excess
  returns?*
- §12: market-profile conformance must cover calendars, **costs**,
  benchmarks, and data-quality rules.

The current protocol does not meet that bar.

| Surface | Gap |
| --- | --- |
| `MarketProfile.cost_bps` | Declared (`5.0` US equity, `10.0` crypto) and tested as a constant. **Never applied** to strategy returns. DSR, walk-forward, vs-random, vs-buy-hold, and vs-benchmark all see gross returns. |
| `compute_strategy_returns` | Lagged weights × asset returns only. No turnover cost. |
| `walk_forward_cv` | Each fold calls `strategy_fn(test_prices)` on the **isolated test window**. Lookback signals (RSI, 12-1 momentum) are cold-started and often all zeros. Train and test abut with **no embargo**. López de Prado Ch. 7 leakage. |
| Gate adapter windows | `train = min(40, n//3)`, `test = min(10, n//8)` — too short for 12-1 momentum (needs `lookback + skip` bars of history). |
| `method_parameter_grid` | `momentum_12_1` searches `skip ∈ {default, 42, 63}`. Jegadeesh and Titman (1993) vary **formation length** (3–12 months) with a short skip, not a 3-month skip that changes the economic story. `lookback` is hardcoded at 252. |

This cycle closes those gaps. It does not reopen product locks (no
alpha promise, constrained DSL, no `FakeWorker` in morning e2e,
`llm_judge` is not a gate, frozen `alphaloop.live`).

## 2. Best-practice basis

### 2.1 Validate net of costs, from turnover

Jegadeesh and Titman (1993, *Journal of Finance*) report relative-strength
profits **after a one-way transaction cost**, using observed turnover
(semiannual turnover ≈ 84.8%; net risk-adjusted return still quoted
after 50 bps one-way). Lesmond, Schill, and Zhou (2004, *Journal of
Financial Economics*) show that ignoring realistic costs overstates
momentum. The PRD already names “failure after transaction costs” as a
stop reason.

**Practice:** one-way `cost_bps` from the frozen market profile;
turnover at bar `t` is the absolute change in the lagged position that
earns the bar’s return; net return = gross − turnover × `cost_bps` /
10 000. Same cost path for every hard gate.

Bailey and López de Prado (2014), Deflated Sharpe Ratio, correct
selection bias on the **observed Sharpe of the evaluated return
series**. If that series is gross, DSR rubber-stamps a cost-ignoring
backtest. Costs belong in the series, not in a later footnote.

### 2.2 Walk-forward must not leak, and must keep lookback history

López de Prado, *Advances in Financial Machine Learning* (2018),
Chapter 7: standard CV leaks because labels overlap in time.
**Purging** drops train observations whose information interval
overlaps the test window. **Embargo** leaves a gap after train (and
around test) so serial correlation does not leak. Hudson & Thames
notes and purged-CV implementations use the same pair of controls.

Walk-forward is the first-release CV (not full combinatorial purged
CV / CPCV). It still must:

1. Compute signals on prices **through the end of the test window**
   so lookbacks see train (and embargo) history, then score **only
   test-bar returns**.
2. Insert `embargo_size` bars between last train bar and first test
   bar (`embargo_size >= 1` in the overnight gate adapter).
3. Fail closed (missing gate → `INCONCLUSIVE`) if the series is too
   short for one purged fold — do not treat “no folds” as
   `NO_EVIDENCE`.

### 2.3 Search method variants that the literature actually uses

Jegadeesh and Titman vary **formation** (3, 6, 9, 12 months) and
holding, with a short skip of the most recent week/month (short-term
reversal). Bailey/LdP DSR then treats those variants as trials.

**Practice:** method search for `momentum_12_1` is formation lookback
at 6m / 9m / 12m with skip fixed at the one-month default (21 daily
bars). That is a methodology repair under PRD §6.1, not a new
economic hypothesis. Do not search 63-bar skips as if they were the
same 12-1 mechanism. Unknown DSL kinds still have only `{}`.

## 3. In-scope requirements

### R1. Net-of-cost strategy returns

`compute_strategy_returns(prices, weights, *, cost_bps: float = 0.0)`
MUST:

- Keep today’s lag: position at `t` is `weights.shift(1)` (no
  look-ahead).
- Gross return = position × asset `pct_change`.
- Turnover at `t` = absolute change in that lagged position
  (`position.diff().abs()`, first bar 0).
- Cost return = turnover × `cost_bps / 10_000`.
- Net = gross − cost.
- `cost_bps == 0` reproduces today’s series (existing tests stay).

`run_protocol` MUST pass `profile.cost_bps` into this function. The
gate runner’s `strategy_returns` argument is therefore net of costs.

### R2. Walk-forward uses history, embargo, and the same cost path

`walk_forward_cv` gains:

- `embargo_size: int = 0` (existing unit tests keep default 0).
- `cost_bps: float = 0.0`.

For each fold:

- Train window: `[i, i + train_size)`.
- Embargo: next `embargo_size` bars unused as train or test.
- Test window: next `test_size` bars.
- `strategy_fn` is called on `prices.iloc[: test_end]` (history
  through test end), not on the isolated test slice.
- Fold OOS (and train) returns are slices of
  `compute_strategy_returns` on that history, so lag and costs are
  consistent across the embargo boundary.

Need `train_size + embargo_size + test_size` bars. Existing error
when `len(prices) < train_size + test_size` becomes
`train_size + embargo_size + test_size`.

The overnight `walk_forward` adapter MUST:

- Set `embargo_size = max(1, profile.periods_per_year // 52)` (~one
  week).
- Pass `cost_bps=profile.cost_bps`.
- Prefer `train_size=periods_per_year`, `test_size=periods_per_year
  // 4` when the series is long enough for one embargoed fold;
  otherwise `train_size=max(20, n // 2)`, `test_size=max(10, n // 8)`
  if that still fits; otherwise skip the gate (exception → missing
  result → `INCONCLUSIVE`), not a fake `passes=True`.

DSR / vs_* adapters keep using the caller’s net `strategy_returns`.
`GateResult.detail` for those rows SHOULD include `cost_bps` when
the profile cost was applied (copy from the profile in
`run_hard_gates`).

### R3. Economically motivated `momentum_12_1` method grid

`momentum_12_1(prices, skip=21, lookback=252)`: `lookback` replaces
the hardcoded 252. Need `lookback + skip` bars or return zeros
(same fail-closed warmup as today).

`method_parameter_grid("momentum_12_1")` MUST be exactly:

```text
({}, {"lookback": 126, "skip": 21}, {"lookback": 189, "skip": 21})
```

- `{}` = 12-month formation, 1-month skip (defaults).
- 126 ≈ 6 months, 189 ≈ 9 months, skip stays 21.
- Still `RevisionKind.METHOD` (parameter-only).

`rsi` and `roc` grids MAY stay as they are (`rsi`: `{}`, window 21,
window 28; `roc`: `{}`, window 40). Unknown kinds remain `({})`.

### R4. Tests

- Unit: costs reduce net returns when turnover > 0; zero cost
  matches the old series; lookback parameter changes warmup;
  walk-forward `strategy_fn` sees length ≥ train+embargo+test;
  embargo leaves `embargo_size` bars between `train_end` and
  `test_start`; momentum grid is the triple above.
- Integration: `run_hard_gates` with a high-turnover strategy
  records `cost_bps` in detail; DSR `observed_sharpe` is lower at
  `cost_bps=1000` than at `0` when weights flip; protocol loop
  passes profile costs into returns (mock or real `run_protocol`).
- E2E: existing real-daemon Chromium matrix still passes. Do not
  invent `FOUND`. Do not add `FakeWorker` to e2e.

## 4. Out of scope

- Full combinatorial purged CV (AFML Ch. 12). Embargoed walk-forward
  is the first-release CV.
- Nonlinear market-impact models, bid-ask bounce, or per-name
  liquidity filters (need volume data the first-release parquet
  does not require).
- Changing frozen `HOST_CONSTRAINT`, unfreezing live/SPA, treating
  `llm_judge` as a gate.
- Expanding the DSL to new kinds.
- Soak / 95% overnight benchmark (release process).

## 5. Acceptance

A candidate that only “works” on gross returns, or that only looks
good because walk-forward refit signals on a 10-bar island, cannot
reach `FOUND`. Method search for 12-1 momentum is 6/9/12-month
formation with a one-month skip. Existing zero-cost and embargo-0
tests remain green.

## 6. Loop exit

After this cycle, remaining research-method items are larger than a
first-release patch: CPCV, capacity/ADV filters, protocol preview
before freeze, soak. If nothing else is first-release-sized without
reopening locks, stop the loop.
