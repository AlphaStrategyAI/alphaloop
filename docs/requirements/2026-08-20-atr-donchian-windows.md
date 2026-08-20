---
title: "ATR breakout Donchian / Turtle lookbacks"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-pairs-formation-windows.md
---

# ATR breakout Donchian / Turtle lookbacks

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** How `atr_breakout` method search is parameterized. Not
Turtle position sizing, short entries, or 10-day exits. Not CPCV.
Not a change to locked product positioning.

## 1. Why this cycle exists

`atr_breakout` is already scorable overnight (close-only OHLC
wrapper, Wilder ATR 14). Its grid is still `({})`: one trial,
`breakout_window=50`, which is **not** a Donchian / Turtle entry
length.

Richard Dennis’s Turtle rules (as recorded in Faith, *Way of the
Turtle*, and the original Turtles trading system documentation)
use two Donchian entries: **System 1 = 20-day breakout**, **System
2 = 55-day breakout**. ATR (`N`) sizes the position; this lab’s
factor uses ATR as a buffer on a close breakout, with Wilder’s
**14** as `atr_window`. Searching only 50 days never evaluates the
originating breakout lookbacks (PRD §6.1 insufficient parameter
coverage).

Do not grid `atr_multiplier` or flip to short breakdowns — those
change the economic rule. Do not grid `atr_window`; Wilder 14
stays the ATR default (`{}` keeps 50-day breakout so existing
specs do not silently change).

## 2. Best-practice basis

1. **Predeclare originating Donchian entries.** Turtle S1/S2 20 /
   55. Donchian (1970s) channel default on many platforms is 20.
2. **Three points.** Default 50, Turtle 20, Turtle 55.
3. **Keep ATR period as Wilder 14** unless a later cycle adopts
   Turtle `N` = 20-day ATR for sizing (out of scope: this factor
   does not size).

## 3. In-scope requirements

### R1. Method grid

```text
atr_breakout: (
  {},
  {"breakout_window": 20},
  {"breakout_window": 55},
)
```

All points `RevisionKind.METHOD`. Other grids unchanged.
`atr_breakout()` defaults unchanged.

## 4. Out of scope

- 10-day Turtle exit, 2×ATR stops, unit sizing.
- Parkinson / OBV grids (feature / needs volume).
- CPCV, nested holdout, soak.

## 5. Acceptance

- Unit: grid is the three dicts; 20 vs 55 changes the weight
  series; weights stay in `[0, 1]`.
- Integration: protocol walks three trials when the first two are
  incomplete.
- E2E: Chromium matrix still passes. Overnight worker and morning
  job with `atr_breakout` record ledger rows of that kind. Do not
  invent `FOUND`.

## 6. Loop exit

Remaining first-release search: 50-day Bollinger, Parkinson not a
signal. Remaining validation: CPCV/PBO, nested holdout, median
fold Sharpe.
