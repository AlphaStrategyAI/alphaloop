---
title: "Chronological regime stability and Appel MACD grids"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-19"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-19-oos-dsr-method-grids.md
---

# Chronological regime stability and Appel MACD grids

**Date:** 2026-08-19
**Status:** Approved for this implementation cycle
**Scope:** How walk-forward decides pass/fail when concatenated OOS
returns are long enough to split in half, and how MACD method search
is parameterized. Not CPCV, PBO, or a new `HardGateName`. Not a
change to locked product positioning.

## 1. Why this cycle exists

The previous cycle scored DSR and benchmark gates on concatenated
walk-forward OOS returns, and searched RSI/ROC on literature windows.
Two honesty gaps remain.

### Validation

`walk_forward_cv` still sets `passes` from **mean fold OOS Sharpe >
0** alone. A candidate can be long in a rising first half of the
holdout, lose that edge in the second half, and still pass because
the average of fold Sharpes stays slightly positive.

PRD §6.2 lists **instability across required regimes** as a reason
that does **not** justify further parameter search.
`FORBIDDEN_CONTINUE_REASONS` already contains `regime_unstable`, but
nothing in the diagnostic or overnight adapter ever produces that
condition. The morning page can therefore show `walk_forward: pass`
for a path that is not stable across chronological subperiods of the
same OOS concat the lab now treats as the reported track record.

Harvey and Liu (2015), *Backtesting*, *Journal of Portfolio
Management*, treat a chronological IS/OOS split as the natural
check that an in-sample winner is not a single-regime artifact, and
prefer survivors that also pass a full-sample multiple-test. This
lab already has DSR on the OOS concat. What it lacks is the cheap
half-sample check: both chronological halves of that concat should
themselves have positive Sharpe. López de Prado, *Advances in
Financial Machine Learning*, Ch. 7–12, warns against fitting one
market regime; combinatorial purged CV is the full answer and is
**out of scope**. A midpoint split of the already-computed OOS
series is the first-release-sized stand-in.

Bailey and López de Prado (2012) note that Sharpe inference is
unreliable below about **30** observations. Failing a 20-bar OOS
path as “regime unstable” would mint false `NO_EVIDENCE`. Short
series keep today’s mean-only rule.

Folding the check into the existing `walk_forward` gate avoids a
seventh `HardGateName`. Existing frozen specs
(`dsr, walk_forward, vs_benchmark`) stay complete. A failed half
shows up as `walk_forward: fail`, which `should_continue` already
maps to `hard_gate_failed`. Wiring `stop_reason=regime_unstable` is
unnecessary this cycle.

### Search

`macd` is a first-class DSL kind. `method_parameter_grid("macd")` is
still `({})` — one trial, the street default `(12, 26, 9)`.

Appel (1979) did not publish `(12, 26, 9)` as *the* MACD. Kang,
Kim, and Leigh (2021), “Improving MACD Technical Analysis…”,
*Journal of Risk and Financial Management* 14(1):37, and Murphy
(1999), *Technical Analysis of the Financial Markets*, p. 253,
record Appel’s original daily settings: **(8, 17, 9) for buys** and
**(12, 25, 9) for sells**. `(12, 26, 9)` became the platform
default later (six-day weeks → two weeks / one month / 1.5 weeks).
Searching only the default, while RSI and 12-1 already walk
originating literature variants, is incomplete method coverage
(PRD §6.1), not an economic-logic change.

## 2. Best-practice basis

1. **Do not trust a single-regime OOS average.** Harvey & Liu
   (2015); Arnott, Harvey, and Markowitz (2019), “A Backtesting
   Protocol.” If the reported series is the walk-forward concat,
   both chronological halves of that series should support the
   claim.
2. **Too-short samples are not a regime fail.** Bailey & López de
   Prado (2012) ~30-observation floor — same constant as DSR.
3. **Do not add a new frozen gate this cycle.** Completeness is
   defined by the user’s predeclared set. Folding into
   `walk_forward` keeps existing specs valid.
4. **Predeclare economically motivated MACD grids.** Appel via
   Murphy (1999) and Kang et al. (2021). Each point remains a
   PRD §6.1 method repair and counts in `n_trials`. Do not grid
   `signal_period`; both Appel settings keep 9.

## 3. In-scope requirements

### R1. Chronological half Sharpes

A helper MUST split a return series at the midpoint
(`n // 2`) and return annualized Sharpe on each half plus whether
the split was evaluated.

- If `len(returns) < 30`, the split is **not evaluated**:
  half Sharpes are `0.0`, and callers MUST NOT treat the series as
  unstable.
- If `len(returns) >= 30`, both halves are scored with the same
  annualized Sharpe function walk-forward already uses.

### R2. Walk-forward pass requires both halves when evaluated

`WalkForwardResult` MUST include:

- `first_half_sharpe: float`
- `second_half_sharpe: float`
- `regime_stable: bool`

When the OOS concat has length `>= 30`:

- `regime_stable` is true iff both half Sharpes are `> 0`.
- `passes` is true iff **mean fold OOS Sharpe > `min_oos_sharpe`**
  **and** `regime_stable`.

When the concat is shorter than 30, `regime_stable` is true
(not evaluated) and `passes` stays the mean-fold rule. Zero folds
still fail (`passes=False`).

The overnight adapter MUST copy `first_half_sharpe`,
`second_half_sharpe`, and `regime_stable` into the `walk_forward`
gate `detail` (same `_detail` path as `oos_sharpe_mean`).

### R3. No new `HardGateName`

Do not add `regime_stability` to the gate enum. Do not change
`FORBIDDEN_CONTINUE_REASONS`. Do not set `stop_reason` to
`regime_unstable` this cycle. A failed half is a failed
`walk_forward` gate.

### R4. MACD method grid

```text
macd: ({}, {"fast": 8, "slow": 17, "signal_period": 9}, {"fast": 12, "slow": 25, "signal_period": 9})
```

`{}` keeps the factor default `(12, 26, 9)`. RSI, ROC, and
`momentum_12_1` grids are unchanged. Unknown kinds remain `({})`.
All listed MACD points stay `RevisionKind.METHOD`.

## 4. Out of scope

- Combinatorial purged CV and PBO (AFML Ch. 12).
- Named economic regimes (vol quintiles, NBER dates, bull/bear
  labels). Chronological halves of OOS are the only split.
- Changing DSR math, embargo, or costs.
- Volume/ADV capacity gates.
- Protocol preview UX, soak, MCP, unfreezing live/SPA.

## 5. Acceptance

- Unit: helper skips evaluation below 30 bars; helper reports a
  negative second half; walk-forward fails when the first OOS half
  is up and the second is down even if mean fold Sharpe is
  positive; positive-drift buy-and-hold still passes; MACD grid is
  the three Appel/default points and each is `METHOD`.
- Integration: `run_hard_gates((WALK_FORWARD,), ...)` on a real
  (not mocked) walk-forward includes `regime_stable` in `detail`.
- E2E: existing real-daemon Chromium matrix still passes. A
  `macd` + `walk_forward` overnight/worker run writes
  `regime_stable` into `evidence/gates.json`. Default e2e YAML that
  only requires `dsr` stays full-sample and does not invent
  `FOUND`.

## 6. Loop exit

After this, remaining research-method work is CPCV/PBO, capacity
filters, nested final holdout beyond walk-forward, correlation-
adjusted \(N_{\text{eff}}\) for DSR, soak. If nothing else is
first-release-sized, stop.
