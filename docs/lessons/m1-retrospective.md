# M1 Retrospective — openstrategy.diagnostic

> **Coder Self-Harness Protocol applied retroactively to M1.**
> Originally the failures section lived in `.claude/loop-diagnostic-m1.md`
> (which is gitignored). This file is the project-versioned equivalent
> that future contributors (and future me) can read.

## Context

- Goal: [[openstrategy v1.0 goal]] — "honest verifiable quant research"
- M1: `openstrategy.diagnostic` package + 3 core functions + vs SPY
- Result: 49 unit tests (target 30+), 82/82 total tests pass, commit
  `9636510`. M1 marked DONE in `.claude/loop-diagnostic-m1.md`.

## Failures During M1

### 1. `vs_random` used the wrong test statistic

- **Pattern**: comparing strategies via block-shuffled baseline
  using Sharpe ratio.
- **Where**: `src/openstrategy/diagnostic/benchmarks.py:vs_random()`
- **Tried**: p_value = fraction of random baselines whose Sharpe >= ours.
- **Root cause**: block-shuffling preserves the marginal return
  distribution, so `random_sharpe_mean ≈ strategy_sharpe` and
  `p_value ≈ 0.5` for *every* strategy. The test is trivially
  inconclusive — Sharpe is not order-sensitive.
- **Fix**: switch to max-drawdown as the test statistic. Trend
  strategies have shallow max-DD; shuffled baselines have deep
  max-DD. `passes = strategy_max_dd > median(random_max_dds)`.
- **Lesson**: when testing for *temporal* signal, the test
  statistic must itself be order-sensitive. Sharpe ratio / mean /
  std / VaR are not. Max-drawdown, Sortino, LPM, time-to-recovery
  are.

### 2. `data_source_consistency` test assumed raw-length overlap

- **Pattern**: asserting `n_overlap == 200` when slicing two
  `pd.date_range` series offset by 100.
- **Where**: `tests/diagnostic/test_consistency.py:test_inner_join_aligns_correctly`
- **Tried**: `pd.date_range("2024-01-01", periods=100, freq="B")` and
  `pd.date_range("2024-06-01", periods=100, freq="B")` → expected 200
  overlap.
- **Root cause**: B (business day) frequency skips weekends. Two
  ranges starting on different days have different work-day
  offsets, so raw `len` is not 200. Need a single shared index
  and explicit slicing.
- **Fix**: build one `full_idx = pd.date_range(..., periods=300, freq="B")`,
  then `a` uses `full_idx[:200]`, `b` uses `full_idx[100:]`. Inner
  join is exactly 100.
- **Lesson**: when index is business-day or has irregular holidays,
  the only way to know overlap length is to compute the inner join.
  Don't try to predict it from raw lengths.

### 3. `p95` test used a single-bar 30% spike

- **Pattern**: asserting `p95_rel_error > 0.05` after injecting one
  30% spike in a 500-bar series.
- **Where**: `tests/diagnostic/test_consistency.py:test_p95_rel_error_catches_tail_events`
- **Tried**: 1 bar × 30% bias.
- **Root cause**: p95 is the 95th percentile. One bar is 0.2% of
  500; p95 sees the *other 475 normal bars* before the spike, so
  p95 ≈ 0. To make p95 > 0, you need ≥5% of bars biased.
- **Fix**: bias 10% of bars by 5% each. Now p95 catches the cluster.
- **Lesson**: percentile-based thresholds (p95, p99, median) all
  need a *minimum fraction* of affected samples to register. A
  single point never moves p95.

### 4. DSR pulled in `scipy` as a hidden dependency

- **Pattern**: import `scipy.stats` for `norm.cdf` and `norm.ppf`.
- **Where**: `src/openstrategy/diagnostic/dsr.py`
- **Tried**: standard `from scipy import stats`.
- **Root cause**: `diagnostic` is supposed to be zero-dep apart from
  `numpy` / `pandas`. Forcing `scipy` on users adds a transitive
  build dep (FORTRAN compiler for some versions) for a single CDF.
- **Fix**: hand-rolled `_norm_cdf` via `math.erf` and `_norm_ppf`
  via the Beasley-Springer-Moro rational approximation. ~30 lines,
  no new dep, error <1e-7.
- **Lesson**: for "obviously numerical" code (normal CDF, LPM,
  log-sum-exp), check if you can do it in pure Python / numpy
  before reaching for scipy. The few extra lines of math are
  cheaper than a build dep.

### 5. M1 itself violated the Coder Self-Harness Protocol

- **Pattern**: ran M1 to completion, then wrote `state.last_result = DONE`
  in the loop file — and stopped. No `failures:` block.
- **Where**: `.claude/loop-diagnostic-m1.md` (the original write)
- **Tried**: nothing — I forgot the reflection step entirely.
- **Root cause**: I treated the loop file as a todo list / status
  tracker, not as the Coder-mandated reflection log. The protocol
  (per `~/.hermes/profiles/coder/CLAUDE.md`) explicitly requires
  appending `failures:` at end-of-task. I bypassed it because I
  was running in `default` profile, not `coder`.
- **Fix**: this file. (1) Hand-filled 4 actual bugs from M1 above.
  (2) Added a 5th: the meta-failure of skipping the protocol. (3)
  Future M2–M4 should be run from `coder` profile so the
  protocol fires automatically.
- **Lesson**: profile choice matters. Each Hermes profile carries
  a different SOUL + CLAUDE.md. `default` is for general chat;
  `coder` is for code with a `loop-*.md` state file. Switching
  to the right profile is the first step, not the last.

## How to Use This File

- **Before M2**: re-read this list. Each entry above should have
  been avoided in M2. If a similar pattern reappears, it's a
  signal the Coder profile isn't being used.
- **In M2 review**: any new failures get appended as `## Failures
  During M2` section below.

## Failures During M2

*(to be appended after M2 completes)*
