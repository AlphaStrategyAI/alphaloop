---
title: "Pairs spread universe hedge and formation windows"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-williams-pct-r-grid.md
---

# Pairs spread universe hedge and formation windows

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Make `pairs_spread` scorable overnight when the frozen
universe has two or more names, and search Avellaneda–Lee / GGR
z-score windows. Not pair *selection*. Not CPCV. Not a change to
locked product positioning.

## 1. Why this cycle exists

### Validation

`pairs_spread` is a first-class DSL kind. Overnight `_call_factor`
requires `parameters.hedge_asset` in the price map. Frozen specs
carry the pair in `market_scope` (`AAPL, MSFT`) but method grids
do not (and must not) inject a hedge ticker — that would be a
market-scope change (PRD §6.1). Result: a user who freezes pairs
mean-reversion never gets a complete gate set; the worker raises
`UnsupportedDslError` instead of `FOUND` / `NO_EVIDENCE` /
`INCONCLUSIVE` from evidence.

If the universe has a second name, that name **is** the hedge.
Using it is an ambiguous-implementation repair, not a new
hypothesis.

A one-name universe still cannot score a pair; keep raising.

### Search

The z-score window is hardcoded via `{}` at **60** bars.
Avellaneda and Lee (2010), “Statistical Arbitrage in the US
Equities Market,” estimate residuals on a **60-day** trailing
window (about one earnings cycle) — that default stays. Gatev,
Goetzmann, and Rouwenhorst (2006), *Review of Financial Studies*,
form pairs over **12 months** and trade **6 months**. Searching
only 60 days never evaluates those formation lengths as the
z-score lookback (the closest method analogue this factor has;
it does not do distance-based pair *selection*).

## 2. Best-practice basis

1. **Declared methods must be scorable** when the frozen scope
   supplies the missing input (same as close-only Williams %R).
2. **Predeclare originating windows.** Avellaneda–Lee 60;
   GGR 6-month / 12-month as 126 / 252 business days.
3. **Do not grid the hedge ticker.** Universe is frozen.

## 3. In-scope requirements

### R1. Default hedge from universe

When `kind == "pairs_spread"` and `hedge_asset` is missing,
`target_weights` MUST set `hedge_asset` to the first universe
name that is not the asset being weighted. If none exists, keep
today’s `UnsupportedDslError`.

Explicit `hedge_asset` still wins.

### R2. Method grid

```text
pairs_spread: (
  {},
  {"window": 126},
  {"window": 252},
)
```

`{}` keeps window 60 / num_std 1.5. Do not list `hedge_asset`.
All points are `RevisionKind.METHOD`. Other grids unchanged.

## 4. Out of scope

- Distance-method pair selection, OLS hedge ratio, short leg.
- `num_std` sweep, CPCV, volume/ADV, soak.

## 5. Acceptance

- Unit: grid is the three dicts; no `hedge_asset` in grid points;
  window 126 vs 252 changes the weight series.
- Integration: two-name universe without `hedge_asset` returns
  finite weights; one-name universe still raises; protocol walks
  three trials when the first two are incomplete.
- E2E: existing Chromium matrix still passes. Overnight worker
  and morning job with `pairs_spread` and `AAPL, MSFT` record
  ledger rows of that kind. Do not invent `FOUND`.

## 6. Loop exit

Next: ATR/Donchian 20/55 breakout windows. Then CPCV / nested
holdout.
