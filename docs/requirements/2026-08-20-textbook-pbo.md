---
title: "Textbook S=16 CSCV PBO when the sample is long enough"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "docs/requirements/2026-08-20-pbo-selection.md — additive partition upgrade"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-pbo-selection.md
  - docs/requirements/2026-08-20-textbook-cpcv.md
---

# Textbook S=16 CSCV PBO when the sample is long enough

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Prefer AFML / Bailey CSCV `S=16` (`C(16,8)` paths) for
probability of backtest overfitting when the aligned return series
are long enough. Keep `S=6` (`C(6,3)=20`) on shorter samples. Not a
new `HardGateName`. Not inventing `FOUND`. Not shrinking DSR `n_trials`.

## 1. Why this cycle exists

CPCV now uses textbook `S=16` when the inner sample allows. PBO still
ranks selection on `C(6,3)=20` CSCV paths. A multi-trial `FOUND` can
pass that coarse combinatorics and fail the partition López de Prado
published for overfitting probability.

PBO is the selection check: among the trials we actually scored, how
often is the in-sample winner the out-of-sample loser? It must sit on
the **same group count** as CPCV so the overnight lab does not have
two different notions of "enough calendars."

Raising `S` can only make a would-be `FOUND` fail or stay unevaluated.
It must not skip PBO on short samples that already evaluate `S=6`.
DSR still uses unique-ledger `n_trials`, not PBO paths.

## 2. Best-practice basis

1. **Bailey & López de Prado (2014), AFML Ch. 12:** `S=16` groups,
   in-sample size `S/2=8` → `C(16,8)=12870` paths. Floor
   `len >= 16 * min_group_bars` (320 bars), same as CPCV.
2. **Same fallback as CPCV:** `S=6` when `120 <= len < 320`. Not
   evaluated below 120 bars or when `N < 2`.
3. **Vectorized path Sharpes:** 12870 Python `pd.Series` loops would
   punish a local overnight job. Column Sharpes on boolean masks must
   match the existing `ddof=1` definition.
4. **Do not invent `FOUND`.** Do not feed PBO paths into DSR.

## 3. In-scope requirements

### R1. Auto partition

`probability_of_backtest_overfitting` uses `select_cpcv_shape(n)`'s
group count when `n_groups` is omitted: 16 or 6 or unevaluated.
Explicit `n_groups` still wins. When evaluated,
`n_paths == C(n_groups, n_groups // 2)`.

### R2. Attach fields

`_attach_pbo` also copies `pbo_n_groups`. Existing `pbo`,
`pbo_n_strategies`, `pbo_n_paths`, `pbo_passes` remain.
`MORNING_DETAIL_KEYS` includes `pbo_n_groups`.

### R3. Locks

`HOST_CONSTRAINT` unchanged. No `FakeWorker` in morning e2e. No gate
override. Correlation-adjusted \(N_{\mathrm{eff}}\) is out of scope
and must not reduce DSR `n_trials` in this cycle.

## 4. Out of scope

- Soak / 95% overnight. \(N_{\mathrm{eff}}\). MCP / cloud workers.
- Unfreezing `webui/`. New YAML PBO checkbox.

## 5. Acceptance

- Unit: 80 bars unevaluated; 180 bars → 20 paths `n_groups==6`; 320
  bars → 12870 paths `n_groups==16`; identical series still pass;
  IS-best/OOS-worst still fail; explicit `n_groups=6` on a long
  series still 20 paths.
- E2E: existing Chromium matrix still legal-outcomes only. Do not
  invent `FOUND`.
  `python3 -m pytest` unit + e2e as usual.

## 6. Loop exit

Remaining validation: soak / 95% overnight (not CI),
correlation-adjusted \(N_{\mathrm{eff}}\) (must not make `FOUND`
easier by shrinking N). Later: MCP / cloud workers. Packaged console
visual presence remains a product gap versus the overnight-lab goal.
