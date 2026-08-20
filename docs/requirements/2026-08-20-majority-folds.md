---
title: "Walk-forward majority of positive folds"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-median-fold-sharpe.md
---

# Walk-forward majority of positive folds

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** How walk-forward decides pass/fail when there are enough
folds to ask whether most of them are profitable. Not CPCV/PBO. No
new `HardGateName`. Not textbook `S=16` combinatorics.

## 1. Why this cycle exists

Median fold OOS Sharpe is already in `passes` when `n_folds >= 3`.
For **odd** fold counts the median being strictly above the threshold
already implies a strict majority of folds are positive. For **even**
fold counts it does not.

Example: fold Sharpes `-1.0, -0.5, 0.6, 2.0`. Mean `0.275`, median
`0.05`, two chronological halves can both be positive if the large
wins dominate each half, yet only **2 of 4** folds made money. A
five-minute morning reader who sees `oos_sharpe_median > 0` would
think the typical fold worked. Half of the OOS windows did not.

`docs/requirements/2026-08-20-median-fold-sharpe.md` §4 deferred
"requiring a majority of folds to pass." This cycle takes that
named remaining check.

López de Prado, *Advances in Financial Machine Learning*, treats the
**distribution** of OOS outcomes as the object of walk-forward. Mean
and median are location statistics. A majority count is a robustness
check: the strategy must win on more paths than it loses, not just
on a right-skewed average of a 50/50 split.

## 2. Best-practice basis

1. **Do not let even-n medians hide a coin-flip.** For `n` even, the
   median of a 50/50 mix of losses and wins can sit just above zero.
2. **Reuse the existing fold Sharpe vector.** No new CV scheme, no
   new hard gate.
3. **Too few folds: skip.** Majority of two points is not a robustness
   check. Same floor as the median rule: require majority only when
   `n_folds >= 3`.

## 3. In-scope requirements

### R1. Majority participates in `passes` when n_folds ≥ 3

A fold is **positive** when its OOS Sharpe is strictly greater than
`min_oos_sharpe` (default `0.0`). Non-finite Sharpes do not count as
positive.

When `n_folds >= 3`, `passes` requires the existing mean, chronological
half, and median checks **and** a strict majority:

```
n_positive_folds * 2 > n_folds
```

That is `n_positive_folds > n_folds / 2`. Four folds need three
positives. Three folds need two. Six folds need four.

When `n_folds < 3`, do not use majority as an extra fail (mean +
regime only; median also skipped). Zero folds still fail.

### R2. Copy the count into gate detail and the morning report

`WalkForwardResult` MUST expose:

- `n_positive_folds: int`
- `majority_stable: bool` — `True` when majority is not evaluated
  (`n_folds < 3`) or when the strict-majority inequality holds.

`_detail` MUST copy both when they are `int` / `bool`.
`MORNING_DETAIL_KEYS` MUST include `n_positive_folds` and
`majority_stable` so `report.md` and the morning evidence lines
show them.

## 4. Out of scope

- Textbook CPCV `S=16` / `C(16,8)`.
- Correlation-adjusted \(N_{\mathrm{eff}}\).
- Soak / 95% overnight as CI.
- Funnel bar charts or other visual polish.
- New `HardGateName`. Changing DSR, costs, embargo, or method grids.

## 5. Acceptance

- Unit: helper on `[-1.0, -0.5, 0.6, 2.0]` at threshold `0.0` returns
  `n_positive=2` and majority not ok. Two Sharpes skip majority.
  Three Sharpes `[-0.1, 0.2, 0.3]` are a majority.
- Unit: four constructed walk-forward folds whose mean > 0, median
  > 0, and both chronological halves > 0, but only two of four fold
  Sharpes > 0 → `passes` is False; `n_positive_folds == 2`;
  `majority_stable` is False. Positive-drift buy-and-hold still
  passes. Two-fold short series does not fail on majority.
- Integration: real walk-forward gate detail includes
  `n_positive_folds` and `majority_stable`.
- E2E: existing Chromium matrix still passes. Overnight
  `walk_forward` evidence records those keys. Do not invent `FOUND`.

## 6. Loop exit

Remaining validation: textbook `S=16` CPCV, soak / 95% overnight
(release process, not CI), correlation-adjusted \(N_{\mathrm{eff}}\)
(reducing N would make `FOUND` easier — keep N = ledger count until
that is designed). Remaining product: visual polish beyond count
funnel; MCP / cloud workers.
