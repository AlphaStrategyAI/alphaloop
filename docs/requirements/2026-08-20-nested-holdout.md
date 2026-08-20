---
title: "Nested final holdout beyond walk-forward, CPCV, and PBO"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-cpcv-walk-forward.md
  - docs/requirements/2026-08-20-pbo-selection.md
---

# Nested final holdout beyond walk-forward, CPCV, and PBO

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** A locked final test window that selection diagnostics never
see. Not a new `HardGateName`. Not `S=16`. Not soak. Not reversing
mid-grid stop on complete gate failure.

## 1. Why this cycle exists

Walk-forward, CPCV, and PBO all currently score the **same full
sample**. A candidate can pass every inner diagnostic and still have
been selected with knowledge of the most recent returns. López de
Prado (AFML) and standard nested validation keep a **final holdout**
embargoed from selection: train/validate (here: WF, CPCV, DSR, vs_*,
PBO) on the inner prefix; confirm on the unused suffix.

That is the remaining named verification gap after CPCV and PBO.

## 2. Best-practice basis

1. **Nested split:** inner prefix for selection; embargo; locked
   suffix for confirmation.
2. **First-release sizes:** holdout = `max(30, periods_per_year // 4)`
   (63 on US equity daily); embargo = `max(1, periods_per_year // 52)`;
   inner must be at least 120 bars (the CPCV floor). Skip the split
   when `n` is too short — same fail-open as CPCV, not an invented
   `FOUND` block on toy series.
3. **Holdout pass:** net-of-cost holdout Sharpe > 0 with at least 30
   observations. Causal `strategy_fn` may see prices through the end
   of the holdout window; only the suffix is scored.
4. **PBO uses the inner prefix** so selection overfitting is not
   measured on the locked suffix.

## 3. In-scope requirements

### R1. `nested_holdout_bounds`

`alphaloop.diagnostic.holdout.nested_holdout_bounds(n, periods_per_year)`
returns `(inner_end, holdout_start, holdout_end)` or `None`.

### R2. Selection on inner; confirm on suffix

`run_hard_gates` runs WF / CPCV / DSR / vs_* on the inner prefix when
bounds exist. After those results, score the holdout and AND
`holdout_passes` into the DSR result if DSR is required, else
walk-forward, else the first result. Detail keys: `holdout_n`,
`holdout_sharpe`, `holdout_passes`.

`data_consistency` still uses the caller frames (not a performance
split).

### R3. PBO inner slice

When `run_protocol` computes PBO, it passes return series truncated
to `inner_end` when bounds exist.

### R4. Morning line

`MORNING_DETAIL_KEYS` includes `holdout_n`, `holdout_sharpe`,
`holdout_passes` when present.

## 4. Out of scope

- New YAML gate. `S=16`. Soak. FakeWorker in morning e2e.
- Inventing `FOUND`. Changing `HOST_CONSTRAINT`.

## 5. Acceptance

- Unit: `n < 187` on 252-period data is `None`; 400-bar buy-and-hold
  records `holdout_passes` true; late crash fails holdout while inner
  DSR would otherwise pass; 80-bar WF has no holdout keys; PBO in the
  protocol loop is called with inner-length series when bounds exist.
- E2E: MACD walk-forward job (260 bars) records `holdout_passes`.
  Legal outcomes only.
