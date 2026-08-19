---
title: "Out-of-sample DSR and literature method grids"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-19"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-19-net-of-cost-validation.md
---

# Out-of-sample DSR and literature method grids

**Date:** 2026-08-19
**Status:** Approved for this implementation cycle
**Scope:** How hard gates consume returns when walk-forward is required,
and how RSI / ROC method search is parameterized. Not full CPCV or
PBO. Not a change to locked product positioning.

## 1. Why this cycle exists

The previous cycle made returns **net of costs** and walk-forward
**history-aware with embargo**. Two honesty gaps remain.

### Validation

`run_hard_gates` still feeds DSR, vs-random, vs-buy-hold, and
vs-benchmark the **full-sample** net return series. Walk-forward is a
separate gate whose only hurdle is “mean fold OOS Sharpe > 0.”

Bailey and López de Prado (2014) apply DSR to the Sharpe that was
**selected and reported**. If that Sharpe is in-sample while the lab
also ran a parameter grid, DSR deflates the wrong number: it
haircuts an overfit statistic instead of the OOS path the morning
page should trust. Practitioner write-ups of the same stack
(walk-forward + DSR, e.g. ARIA Analyst on walk-forward as the gold
standard) treat DSR as a check on the **reported** track record,
paired with OOS testing — not as a second in-sample score.

Bailey and López de Prado (2012), *The Sharpe Ratio Efficient
Frontier*, define **Minimum Track Record Length** and note that the
CLT behind PSR/DSR is typically assumed for samples **longer than
about 30 observations**. A DSR fail on 10 OOS bars is not
`NO_EVIDENCE`; it is `INCONCLUSIVE` (PRD §6.3: available evidence
cannot support a valid judgment).

`vs_random` in the overnight adapter uses `n_simulations=32` and
`block_size=5`. The diagnostic’s own contract defaults to 1000
simulations and a 21-bar block (≈ one trading month). Politis and
Romano (1994) stationary/block bootstrap needs enough resamples for a
stable tail probability; 32 is underpowered for a hard gate.

### Search

`momentum_12_1` now searches Jegadeesh–Titman formation lengths.
`rsi` still searches `{14 default, 21, 28}` and `roc` `{20 default, 40}`
— not the windows the originating literature actually tested.

- Wilder (1978), *New Concepts in Technical Trading Systems*: RSI
  default **14**; he also examined **9** and **21** (and 7, 11, 28).
  9 and 21 are the standard faster/slower method variants on a daily
  chart. Searching 28 while skipping 9 is not that protocol.
- ROC as a simple formation return should use the same 3-month /
  6-month spacing already used for 12-1 lookbacks: **63** and **126**
  business days, with `{}` keeping the factor default (20).

## 2. Best-practice basis

1. **Do not score the search sample.** Arnott, Harvey, and Markowitz
   (2019), “A Backtesting Protocol,” *Journal of Portfolio Management*:
   hold out true OOS; do not data-mine and then test on the same
   sample. When the user predeclares `walk_forward`, the OOS concat
   **is** that holdout. DSR and benchmark gates must use it.
2. **DSR on the reported series.** Bailey & López de Prado (2014).
3. **Too-short samples are inconclusive.** Bailey & López de Prado
   (2012) MinTRL / CLT note (~30 observations).
4. **Block bootstrap with enough draws.** Politis & Romano (1994);
   the in-repo `vs_random` docstring already specifies 21-bar blocks.
5. **Predeclare economically motivated grids.** Wilder (1978) for RSI;
   Jegadeesh–Titman formation spacing for ROC. Each point remains a
   PRD §6.1 method repair and counts in `n_trials`.

## 3. In-scope requirements

### R1. Concatenated OOS returns from walk-forward

`WalkForwardResult` MUST include `oos_returns: pd.Series` — the
concatenation of per-fold test-window **net** returns (same cost path
as today). If test windows overlap (`step_size < test_size`), drop
duplicate index labels, keeping the **first** fold. Zero folds → empty
float series.

### R2. When `walk_forward` is required, score OOS

If `HardGateName.WALK_FORWARD` is in `required`:

1. Run walk-forward **once** (same windows, embargo, costs as today).
2. Use `result.oos_returns` as the return series for `dsr`,
   `vs_random`, `vs_buy_hold`, and `vs_benchmark`.
3. Align buy-hold / benchmark prices to that index (existing
   `_align` / `pct_change` path).
4. Put `returns_scope: "oos_walk_forward"` in those gates’ `detail`.
5. If walk-forward raises or `oos_returns` is empty, those gates are
   **missing** (not `passed=False`) → incomplete evidence →
   `INCONCLUSIVE` when the job completes, never `FOUND`.

If `walk_forward` is **not** required, DSR and vs_* keep using the
caller’s full-sample net `strategy_returns`, with
`returns_scope: "full_sample"`.

### R3. DSR needs at least 30 observations

If the series DSR would use has length `< 30`, omit the DSR result
(missing gate). Do not report `passes=False`. Bailey 2012 CLT floor.

### R4. Overnight `vs_random` power

The overnight adapter MUST call `vs_random` with
`n_simulations=200` and `block_size=21`. Library defaults on
`vs_random()` itself stay (1000 / 21) for non-protocol callers.

### R5. RSI and ROC method grids

```text
rsi: ({}, {"window": 9}, {"window": 21})
roc: ({}, {"window": 63}, {"window": 126})
```

`momentum_12_1` grid is unchanged. Unknown kinds remain `({})`.
All listed points stay `RevisionKind.METHOD`.

## 4. Out of scope

- Combinatorial purged CV and PBO (AFML Ch. 12).
- Changing the DSR formula (annualized SR vs per-period variance).
- Volume/ADV capacity gates.
- Protocol preview UX, soak, MCP, unfreezing live/SPA.

## 5. Acceptance

- Unit: `oos_returns` length equals the sum of unique test bars;
  DSR is called with that series iff walk-forward is required and
  len≥30; DSR omitted when len<30; vs_random adapter kwargs; RSI/ROC
  grids.
- Integration: `run_hard_gates((DSR, WALK_FORWARD), ...)` detail
  `returns_scope == "oos_walk_forward"`; DSR-only remains
  `full_sample`.
- E2E: existing real-daemon Chromium matrix still passes. Default
  e2e specs that only require `dsr` stay full-sample.

## 6. Loop exit

After this, remaining research-method work is CPCV/PBO, capacity
filters, nested final holdout beyond walk-forward, soak. If nothing
else is first-release-sized, stop.
