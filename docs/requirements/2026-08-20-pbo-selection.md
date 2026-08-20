---
title: "Probability of backtest overfitting on multi-trial FOUND"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-cpcv-walk-forward.md
---

# Probability of backtest overfitting on multi-trial FOUND

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Bailey and López de Prado (2014) PBO as a **selection**
check when the frozen protocol has scored two or more trials and is
about to declare `FOUND`. Not a new user-facing `HardGateName`. Not
walking the parameter grid after a complete hard-gate failure. Not
`C(16,8)`. Not overnight soak.

## 1. Why this cycle exists

CPCV asks whether **one** frozen DSL trial is stable across
combinatorial OOS calendars. It does not ask whether the trial we
present as `FOUND` is the one that looked best **in-sample** among
the trials we actually ran.

Bailey, D. H., & López de Prado, M. (2014), "The Probability of
Backtest Overfitting", constructs CSCV paths, picks the in-sample
winner, and asks how often that winner lands in the worse half
out-of-sample. That is the remaining verification gap after CPCV.

PRD §6.2 still holds: a **complete** hard-gate failure does not
justify expanding search. Method repair on **incomplete** evidence
already walks later frozen-grid points and is how `n_trials` becomes
greater than 1. PBO applies to that selection, not to a single-trial
pass.

## 2. Best-practice basis

1. **CSCV / PBO (Bailey & LdP 2014, AFML Ch. 12):** `S=6` groups,
   in-sample combination size `S/2=3` → `C(6,3)=20` paths. Same
   120-bar floor as first-release CPCV (`min_group_bars=20`).
2. **Relative OOS rank of the IS-best.** Rank 1 = lowest OOS Sharpe.
   Overfit path: `rank(IS-best) / N < 0.5`. `PBO` is the fraction of
   paths that are overfit. Pass when `PBO < 0.5`.
3. **N=1 is not selection.** If the first complete trial passes every
   required gate, do not evaluate PBO (degenerate).
4. **Do not feed PBO paths into DSR.** DSR still uses walk-forward
   OOS and unique-ledger `n_trials`.

## 3. In-scope requirements

### R1. `probability_of_backtest_overfitting`

`alphaloop.diagnostic.pbo.probability_of_backtest_overfitting` takes
a sequence of aligned strategy-return series and returns at least:

- `evaluated: bool`
- `pbo: float`
- `n_strategies`, `n_paths`, `n_groups`
- `passes: bool`

Not evaluated when `N < 2` or `len < n_groups * min_group_bars`.
When evaluated, `n_paths == C(n_groups, n_groups // 2)` and
`passes` is `pbo < 0.5`.

### R2. Attach on would-be `FOUND`

When `run_protocol` would return `FOUND` and at least two trials
have scored return series:

- Compute PBO on those series.
- If evaluated, copy `pbo`, `pbo_n_strategies`, `pbo_n_paths`,
  `pbo_passes` onto the DSR result if DSR is required, else onto
  walk-forward, else onto the first result. That result's `passed`
  becomes `passed AND pbo.passes`.
- Rewrite `gates.json` from the attached evidence.
- If the attached evidence no longer `all_passed`, the outcome is
  `NO_EVIDENCE`. Do not walk further grid points (same as a failed
  hard gate).

When PBO is not evaluated, `FOUND` is unchanged.

### R3. Morning line

`MORNING_DETAIL_KEYS` includes `pbo`, `pbo_n_strategies`,
`pbo_n_paths`, `pbo_passes` when present.

## 4. Out of scope

- New YAML hard-gate checkbox / `HardGateName.PBO`.
- Reversing `test_failed_gate_does_not_walk_the_parameter_grid`.
- Textbook `S=16`. Nested holdout. Soak. Inventing `FOUND`.

## 5. Acceptance

- Unit: N=1 not evaluated; identical series evaluate with `pbo < 0.5`
  and pass; constructed IS-best/OOS-worst matrix fails; protocol
  `FOUND` with one passing trial unchanged; incomplete-then-pass
  still `FOUND` when PBO passes; patched failing PBO after two trials
  is `NO_EVIDENCE` and does not start a third trial.
- E2E: existing Chromium matrix still legal-outcomes only. Do not
  invent `FOUND`.
