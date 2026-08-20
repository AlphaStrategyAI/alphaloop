---
title: "Walk-forward median fold OOS Sharpe"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-19-regime-stability-macd-grid.md
---

# Walk-forward median fold OOS Sharpe

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** How walk-forward decides pass/fail when there are enough
folds for a median. Not CPCV/PBO. No new `HardGateName`.

## 1. Why this cycle exists

Walk-forward already stores `oos_sharpe_median` but **ignores it**
when setting `passes`. A single high-Sharpe fold can pull the mean
above zero while most folds lose money. Chronological half Sharpes
catch early/late regime breaks; they miss a **middle** fold that
fails while the two halves of the concat still look fine (up, down,
up).

López de Prado, *Advances in Financial Machine Learning*, treats
the **distribution** of OOS outcomes, not a single average, as the
object of walk-forward. The median of fold Sharpes is already
computed; using it as a second location statistic is the
first-release-sized check. Bailey and López de Prado (2012) ~30
observation floor still applies to concatenated halves; fold count
is separate: require the median only when **n_folds ≥ 3** so a
two-fold run is not failed for having a noisy median.

## 2. Best-practice basis

1. **Do not let one lucky fold carry the mean.** AFML Ch. 12
   motivation without implementing CPCV.
2. **Use a statistic already on the result.** No new CV scheme.
3. **Too few folds: skip.** Median of two points is not a robust
   location check.

## 3. In-scope requirements

### R1. Median participates in `passes` when n_folds ≥ 3

When `n_folds >= 3`, `passes` requires:

- mean fold OOS Sharpe > `min_oos_sharpe` (unchanged),
- `regime_stable` (unchanged),
- **and** `oos_sharpe_median > min_oos_sharpe`.

When `n_folds < 3`, do not use the median as an extra fail
(mean + regime only). Zero folds still fail.

### R2. Copy median into gate detail

`_detail` MUST include `oos_sharpe_median` when it is a float.

## 4. Out of scope

- CPCV, PBO, requiring a majority of folds to pass.
- Changing DSR, costs, embargo, method grids.

## 5. Acceptance

- Unit: three folds with mean > 0, both chronological halves > 0,
  median < 0 → `passes` is False; positive-drift buy-and-hold still
  passes; two-fold short series does not fail on median.
- Integration: real walk-forward gate detail includes
  `oos_sharpe_median`.
- E2E: existing Chromium matrix still passes. Overnight
  `walk_forward` evidence still records `regime_stable` and now
  `oos_sharpe_median`. Do not invent `FOUND`.

## 6. Loop exit

Remaining validation: CPCV/PBO, nested holdout, majority-fold
rule. Remaining search: 50-day Bollinger, OBV (needs volume).
