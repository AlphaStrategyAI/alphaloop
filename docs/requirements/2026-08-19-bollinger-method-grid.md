---
title: "Bollinger Band literature method grid"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-19"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-19-regime-stability-macd-grid.md
---

# Bollinger Band literature method grid

**Date:** 2026-08-19
**Status:** Approved for this implementation cycle
**Scope:** How `bollinger_zscore` method search is parameterized.
Not CPCV/PBO. Not flipping `invert` (that changes mean-reversion
into momentum). Not a change to locked product positioning.

## 1. Why this cycle exists

The previous cycle closed walk-forward chronological-half stability
and gave MACD an Appel grid. Mapping PRD §6.1 (insufficient but
relevant parameter coverage) against `method_parameter_grid` shows
the next first-release-sized search gap.

`bollinger_zscore` is a first-class DSL kind. Its grid is still
`({})`: one trial, the in-repo default **window=20, num_std=1.5,
invert=True**.

John Bollinger (1992), “Using Bollinger Bands,” *Technical Analysis
of Stocks & Commodities* 10(2):47–51, specified **20 periods and 2
standard deviations** as the intermediate-term default, **10 periods
with 1.5 standard deviations** for the short-term trend, and **50
periods with 2.5 standard deviations** for the long-term trend. The
same 20 / 2 defaults remain on bollingerbands.com. Searching only
20 / 1.5 never evaluates the originating calibration, so a
`NO_EVIDENCE` morning for “Bollinger mean reversion” is not a test
of Bollinger’s method.

Flipping `invert` to `False` turns the factor into a breakout /
momentum rule. That is an economic-logic change (PRD §6.1), not a
method repair. The grid MUST NOT include `invert`.

Walk-forward regime halves, OOS DSR, costs, and embargo stay as
they are. Full CPCV remains out of scope.

## 2. Best-practice basis

1. **Predeclare originating calibrations.** Bollinger (1992); do not
   invent a 20 / 1.9 / 21-style numeric sweep.
2. **Keep the frozen default as `{}`.** Existing specs and tests
   that omit parameters still mean 20 / 1.5. Adding 20 / 2 as an
   explicit grid point is the literature repair.
3. **Three points, same as RSI/MACD.** Default, intermediate 20 / 2,
   short 10 / 1.5. Omit 50 / 2.5 this cycle so `n_trials` stays 3
   (DSR haircut stays comparable across kinds).
4. **Do not change economic logic.** No `invert: false`.

## 3. In-scope requirements

### R1. Bollinger method grid

```text
bollinger_zscore: (
  {},
  {"window": 20, "num_std": 2.0},
  {"window": 10, "num_std": 1.5},
)
```

`{}` keeps the factor default `(20, 1.5, invert=True)`. Momentum,
RSI, ROC, and MACD grids are unchanged. Unknown kinds remain
`({})`. All listed Bollinger points stay `RevisionKind.METHOD`.

### R2. Factor API unchanged

Do not change `bollinger_zscore` defaults. Do not add `invert` to
the grid. Existing mean-reversion unit tests keep passing.

## 4. Out of scope

- Combinatorial purged CV and PBO.
- 50-period / 2.5σ long-term point.
- Williams %R (`ohlr_4_pct`) period grid, pairs lookbacks, ATR,
  Parkinson, OBV.
- Volume/ADV capacity, soak, MCP, unfreezing live/SPA.

## 5. Acceptance

- Unit: grid is the three dicts above; each is `METHOD`;
  `bollinger_zscore(..., window=10, num_std=1.5)` still returns
  weights in `[0, 1]`.
- Integration: a `bollinger_zscore` protocol run whose first two
  trials raise incomplete evidence and whose third passes records
  three unique trial ledger ids, matching existing stop policy
  (complete pass or fail does not keep searching).
- E2E: existing real-daemon Chromium matrix still passes. A
  shortened overnight `bollinger_zscore` + `dsr` worker run
  records at least one `bollinger_zscore` ledger row. Do not
  invent `FOUND`. Do not require three overnight trials: a
  complete first-trial DSR stops the grid (PRD §6.2).

## 6. Loop exit

After this, remaining research-method work is CPCV/PBO, capacity
filters, nested holdout, correlation-adjusted \(N_{\text{eff}}\),
50-day Bollinger, Williams %R / pairs grids, soak. If nothing else
is first-release-sized, stop.
