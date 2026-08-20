---
title: "Textbook S=16 combinatorial purged CV when the sample is long enough"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "docs/requirements/2026-08-20-cpcv-walk-forward.md — additive partition upgrade"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-cpcv-walk-forward.md
---

# Textbook S=16 combinatorial purged CV when the sample is long enough

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Prefer AFML Ch. 12 `S=16`, `k=8` combinatorial purged CV on
the existing `walk_forward` gate when the inner sample is long enough.
Keep the first-release `S=6`, `k=2` bound on shorter samples. Not a
new `HardGateName`. Not inventing `FOUND`. Not soak. Not \(N_{\mathrm{eff}}\).

## 1. Why this cycle exists

The product is a **verifiable** overnight lab. First-release CPCV used
`C(6,2)=15` paths because `C(16,8)=12870` looked like a path explosion.
That bound is now the remaining honesty gap: a candidate can still pass
15 coarse calendars and fail the textbook partition López de Prado
actually published.

Bailey / AFML Ch. 12 split the series into **16** contiguous groups and
take every combination of **8** groups as the test set. That is the
standard combinatorial path set. Overnight local jobs can afford it if
`strategy_fn` is called once per group boundary (16 causal prefixes),
not once per path.

PRD: do not invent `FOUND`. Raising the path count can only make
`walk_forward` harder or leave it unevaluated. It must not skip CPCV
on short samples that already evaluate `S=6`.

## 2. Best-practice basis

1. **AFML Ch. 12:** `S=16`, test-set size `k=S/2=8` → `C(16,8)=12870`
   paths. Floor: `len >= S * min_group_bars` with `min_group_bars=20`
   → 320 bars on the series CPCV sees (nested-holdout inner prefix
   when that split exists).
2. **Same causal rule as today:** `strategy_fn` sees prices only
   through each contiguous test span end. Cache by `span_end` so the
   answer equals the uncached loop.
3. **Majority of paths:** match walk-forward. When `n_paths >= 3`,
   `passes` also requires a strict majority of path Sharpes above
   `min_oos_sharpe` (`n_positive * 2 > n_paths`). Mean and median
   remain required.
4. **Fallback, not silence:** if `len < 320` but `len >= 120`, keep
   `S=6`, `k=2`. If `len < 120`, CPCV is not evaluated (unchanged).

## 3. In-scope requirements

### R1. Partition selection

`alphaloop.diagnostic.cv.select_cpcv_shape(n_bars)` returns:

- `(16, 8)` when `n_bars >= 16 * 20`
- `(6, 2)` when `n_bars >= 6 * 20`
- `None` otherwise

`combinatorial_purged_cv` uses that shape when `n_groups` /
`n_test_groups` are omitted. Explicit arguments still win (tests).

### R2. Pass rule and cache

When evaluated:

- `n_paths == C(n_groups, n_test_groups)`
- `passes` is mean > `min_oos_sharpe` **and** median > `min_oos_sharpe`
  **and** majority of path Sharpes when `n_paths >= 3`
- Result includes `n_positive_paths` and `majority_stable`

Implement the span-end cache. Do not feed CPCV paths into DSR.

### R3. Walk-forward detail

When CPCV is evaluated, `walk_forward` detail MUST include existing
`cpcv_*` fields plus `cpcv_n_groups`, `cpcv_n_test_groups`,
`cpcv_n_positive_paths`. Gate `passed` remains WF ∧ CPCV (∧ holdout
when attached). Morning `MORNING_DETAIL_KEYS` copies the new keys.

## 4. Out of scope

- Soak / 95% overnight. Correlation-adjusted \(N_{\mathrm{eff}}\).
- MCP / cloud workers. Unfreezing `webui/`. Changing `HOST_CONSTRAINT`.
- Raising PBO from `S=6` in this cycle.

## 5. Acceptance

- Unit: 80 bars not evaluated; 180 bars → 15 paths; 320 bars → 12870
  paths; positive-drift buy-and-hold passes both shapes; negative
  drift fails; explicit `(6, 2)` still works on a long series.
- Gate: 400-bar positive walk-forward (inner prefix ≥ 320) records
  `cpcv_n_groups == 16` and `cpcv_n_paths == 12870`.
- E2E: 260-bar morning jobs still legal-outcomes only; CPCV may remain
  `S=6` on that inner length. Do not invent `FOUND`.
  `python3 -m pytest` unit + e2e as usual.

## 6. Loop exit

Remaining product after this cycle shipped: textbook `S=16` CSCV PBO
(`docs/requirements/2026-08-20-textbook-pbo.md`). Remaining
validation: soak / 95% overnight (not CI), correlation-adjusted
\(N_{\mathrm{eff}}\). Later: MCP / cloud workers.
