---
title: "Williams %R overnight adapter and literature grid"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-19-bollinger-method-grid.md
---

# Williams %R overnight adapter and literature grid

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Make `ohlr_4_pct` (Williams %R) actually runnable under
the overnight close-only protocol, expose its lookback, and search
Williams’ oversold calibration. Not CPCV. Not renaming the DSL kind.
Not a change to locked product positioning.

## 1. Why this cycle exists

Mapping PRD §6.1–6.2 against first-class DSL kinds:

### Validation

`atr_breakout` already builds a close-only OHLC frame
(`high = low = close`) so walk-forward and DSR can score it.
`ohlr_4_pct` is also an OHLC factor, but `_call_factor` still
passes a **price Series** as if it were a DataFrame. Overnight
`target_weights` then raises (`ohlc["high"]`). A user who freezes
Williams %R cannot obtain a complete gate set; the job fails
technically instead of returning `FOUND` / `NO_EVIDENCE` /
`INCONCLUSIVE` from evidence. That is not a valid validation of
the method.

Close-only `high = low = close` is still a valid %R: the N-bar
high/low of those series is the N-bar high/low of close, which is
the standard close-only approximation when the overnight parquet
has no high/low.

### Search

The lookback is hardcoded to **14**. The default `threshold=0.0`
means “long when %R < 0”, which is almost the entire range
(Williams %R lives in `[-100, 0]`). That is not an oversold rule.

Williams (1979), *How I Made One Million Dollars Last Year Trading
Commodities*: **10-day** lookback; readings **below −80** are
oversold. Platform charts later standardized on **14** periods with
the same −80 / −20 bands (Wikipedia “Williams %R”; StockCharts).
`{}` must keep today’s 14 / 0 behavior so existing tests and specs
do not silently change. The grid must add the originating oversold
rule and the 10-day lookback.

## 2. Best-practice basis

1. **A declared method must be scorable.** If the DSL lists a kind,
   the overnight adapter must feed it a legal input (PRD §6.3:
   technical failure is `failed`, not a research conclusion).
2. **Predeclare originating calibrations.** Williams 10-day and −80
   oversold; keep 14 as `{}`.
3. **Do not invent a numeric sweep.** Three points, same as RSI /
   MACD / Bollinger. `n_trials` stays comparable.

## 3. In-scope requirements

### R1. Close-only overnight adapter

`_call_factor` MUST treat `ohlr_4_pct` like `atr_breakout`:

```python
ohlc = pd.DataFrame({"high": primary, "low": primary, "close": primary})
return fn(ohlc, **kwargs)
```

`target_weights` on a close series MUST NOT raise.

### R2. Expose `period`

`ohlr_4_pct(..., period: int = 14, threshold: float = 0.0)`.
Too-short input is `len < period` (not a hardcoded 14). Default
behavior of `{}` is unchanged.

### R3. Method grid

```text
ohlr_4_pct: (
  {},
  {"threshold": 80.0},
  {"period": 10, "threshold": 80.0},
)
```

`threshold: 80.0` means long when %R < −80 (existing
`pct_r < -threshold` when threshold > 0). All points are
`RevisionKind.METHOD`. Other grids unchanged.

## 4. Out of scope

- Renaming `ohlr_4_pct`. True OHLC parquet columns.
- Williams’ five-day confirmation rule after −100.
- Pairs / ATR / OBV grids, CPCV, capacity, soak.

## 5. Acceptance

- Unit: `period` changes the signal series; threshold 80 still longs a pure
  downtrend; grid is the three dicts; each is `METHOD`.
- Integration: `target_weights` for `ohlr_4_pct` on close series
  returns finite weights; protocol walks three trials when the
  first two are incomplete.
- E2E: existing Chromium matrix still passes. Overnight worker and
  morning job with `signal_mechanism: ohlr_4_pct` record ledger
  rows of that kind. Do not invent `FOUND`.

## 6. Loop exit

Next first-release-sized search items: pairs 12-month window, ATR
Donchian windows. Remaining validation: CPCV/PBO, nested holdout.
