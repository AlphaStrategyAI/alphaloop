---
title: "Combinatorial purged CV on the walk-forward gate"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-median-fold-sharpe.md
---

# Combinatorial purged CV on the walk-forward gate

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** First-release combinatorial purged cross-validation (CPCV)
as an extra location check on the existing `walk_forward` hard gate.
Not PBO. Not a new `HardGateName`. Not nested holdout. Not S=16
combinatorics.

## 1. Why this cycle exists

The product is a **verifiable** overnight lab. Walk-forward plus
chronological halves plus median fold Sharpe still evaluate **one
rolling partition**. A candidate can look stable on that path and
fail on other equally legitimate OOS calendars.

López de Prado, *Advances in Financial Machine Learning*, Chapter 12,
replaces a single walk-forward path with **combinatorial** train/test
group assignments and **purge/embargo** so overlapping labels do not
leak. Bailey and López de Prado's PBO then asks how often the
in-sample winner is the out-of-sample loser. PBO needs a matrix of
many strategies × many paths; this cycle does CPCV for **one frozen
DSL trial**. PBO stays remaining work.

## 2. Best-practice basis

1. **AFML Ch. 12 CPCV:** split the series into `S` contiguous groups;
   every combination of `k` groups is a test set; the complement is
   train. First-release bound: `S=6`, `k=2` → `C(6,2)=15` paths,
   not textbook `C(16,8)`.
2. **Purge + embargo (AFML Ch. 7):** drop `embargo_size` bars at the
   start of each contiguous test span so a label that overlaps the
   preceding train bar is not scored as OOS.
3. **Causal weights:** `strategy_fn` sees prices only through the end
   of each contiguous test span (same lookahead discipline as
   walk-forward).
4. **Do not feed overlapping CPCV paths into DSR.** DSR / vs_* keep
   de-duplicated walk-forward OOS. CPCV is a pass/fail distribution
   over paths, not extra pseudo-observations.

## 3. In-scope requirements

### R1. `combinatorial_purged_cv`

`alphaloop.diagnostic.cv.combinatorial_purged_cv` returns a result
with at least:

- `evaluated: bool`
- `n_groups`, `n_test_groups`, `n_paths`
- `oos_sharpe_mean`, `oos_sharpe_median`
- `passes: bool`

Defaults: `n_groups=6`, `n_test_groups=2`, `min_group_bars=20`.
If `len(prices) < n_groups * min_group_bars`, `evaluated` is False
and `passes` is False (caller ignores `passes` when not evaluated).

When evaluated, `n_paths` equals `C(n_groups, n_test_groups)` and
`passes` requires mean path OOS Sharpe > `min_oos_sharpe` **and**
median path OOS Sharpe > `min_oos_sharpe`.

### R2. Walk-forward gate conjunction

When the `walk_forward` gate runs and CPCV `evaluated` is True:

- `passed` is `walk_forward_cv.passes AND cpcv.passes`
- detail includes `n_folds`, `cpcv_n_paths`, `cpcv_oos_sharpe_mean`,
  `cpcv_oos_sharpe_median`, `cpcv_passes`

When CPCV is not evaluated (short sample), the gate is unchanged
except `_detail` still copies `n_folds` when present.

DSR / vs_* still use walk-forward OOS only.

### R3. Morning evidence line

`format_gate_line` / `MORNING_DETAIL_KEYS` include `n_folds`,
`cpcv_n_paths`, `cpcv_oos_sharpe_mean`, `cpcv_oos_sharpe_median`,
`cpcv_passes` when those keys are present.

## 4. Out of scope

- Probability of backtest overfitting (PBO / CSCV ranking).
- `n_groups=16` / `C(16,8)` path explosion.
- New hard-gate name. FakeWorker in morning e2e. Inventing `FOUND`.
- Changing method grids, costs, or locked `HOST_CONSTRAINT`.

## 5. Acceptance

- Unit: positive-drift buy-and-hold on ≥120 bars evaluates 15 paths
  and passes; negative drift fails; <120 bars is not evaluated;
  WF gate on 400-bar positive drift records `cpcv_passes` true and
  `n_folds`.
- Integration / overnight: walk-forward evidence may include CPCV
  fields when the sample is long enough.
- E2E: existing Chromium matrix still legal-outcomes only; the MACD
  walk-forward job with 260 bars records `cpcv_passes` in gate
  detail. Do not invent `FOUND`.
