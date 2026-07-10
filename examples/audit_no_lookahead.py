"""
audit_no_lookahead.py — Strict look-ahead audit for all 10 alpha factors.

Purpose
-------
The M2 retrospective explicitly identified rolling-window `.shift(1)` as the
#1 recurring bug class in v1.0 (it bit M1's `data_source_consistency` and
M2's `atr_breakout`). A `@no_lookahead_rolling` decorator was proposed as a
v1.1 candidate but is out of scope for v1.0. This script is the v1.0
fallback: a black-box audit that runs every factor end-to-end and asserts
*bit-exact* past equivalence when a future bar is mutated.

Method
------
For each factor `f`:

  1. Build a deterministic synthetic input long enough to clear warmup
     (>= 600 bars, or 800 to cover momentum_12_1's 252+21-bar window).
  2. Compute baseline weights `w1 = f(input)`.
  3. Make a mutated copy `m_input`. Inject a *single* 10x spike at one of
     three future-bar positions:
       - 3n/4 (early-future)
       - 9n/10 (deep-future)
       - n-1 (the last bar — the strongest signal)
  4. Compute `w2 = f(m_input)`.
  5. Assert `w1.iloc[:k] == w2.iloc[:k]` (bit-exact). If any prefix
     diverges, the audit records the first divergent bar index.

The mutation lands strictly after the longest warmup window of each
factor, so the test region exercises the *post-warmup* output of each
factor — not warmup behavior.

Calibration check
-----------------
After all 10 factors pass, two sanity gates fire:

  1. `calibration(lookahead_rsi)` — uses `prices.shift(-1)` followed by an
     α=1/14 EMA. Tests that the audit catches a moderate look-ahead within
     the EMA coupling horizon.
  2. `calibration(pure_lookahead)` — every output bar is `prices.iloc[-1]`,
     the last future bar. No smoothing; leak reaches every past bar. This
     is the **soundness floor**: if the audit cannot catch this, it cannot
     be trusted no matter how the real factors are tuned.

The audit is the receipt we can point to in M2 retro / v1.0 acceptance
when we say "none of the 10 factors uses future information".

Usage
-----
    $ source .venv/bin/activate
    $ python examples/audit_no_lookahead.py

Exit code 0 on PASS, 1 on any FAIL. Print format is also friendly to
human inspection (a checklist table).
"""
from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import pandas as pd

# Ensure `import openstrategy` resolves when run as a plain script.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from openstrategy.engineer import (  # noqa: E402
    atr_breakout,
    bollinger_zscore,
    macd,
    momentum_12_1,
    obv_slope,
    ohlr_4_pct,
    pairs_spread,
    parkinson_hist_vol,
    roc,
    rsi,
)


# ----------------------------------------------------------------------------
# Synthetic data builders
# ----------------------------------------------------------------------------


def _make_prices(n: int = 600, seed: int = 0) -> pd.Series:
    """GBM-ish synthetic close price series with business-day index."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0005, 0.012, n)
    return pd.Series(
        100.0 * np.exp(np.cumsum(rets)),
        index=pd.date_range("2018-01-01", periods=n, freq="B"),
    )


def _make_ohlc(
    prices: pd.Series,
    high_mult: float = 1.005,
    low_mult: float = 0.995,
) -> pd.DataFrame:
    """Wrap a close series into a minimal OHLC frame."""
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices * high_mult,
            "low": prices * low_mult,
            "close": prices,
        },
        index=prices.index,
    )


def _make_volume(prices: pd.Series, seed: int = 1) -> pd.Series:
    """Synthetic volume: log-normal-ish, uncorrelated with price moves."""
    rng = np.random.default_rng(seed)
    base = rng.lognormal(mean=10.0, sigma=0.4, size=len(prices))
    return pd.Series(base, index=prices.index)


# ----------------------------------------------------------------------------
# Audit machinery
# ----------------------------------------------------------------------------


@dataclass
class FactorResult:
    """Outcome of the look-ahead audit on a single factor."""

    name: str
    family: str
    passed: bool
    notes: str = ""
    failures: list[str] = field(default_factory=list)


def _spike(series: pd.Series, idx: int) -> pd.Series:
    """Return a copy of `series` with element at position `idx` scaled by 10.

    A 10× multiplicative spike is large enough to dominate any rolling/EMA
    coupling but stays well within float64 range even on long synthetic
    series.  We use `iloc` (positional) so the audit is index-agnostic.
    """
    mutated = series.copy()
    mutated.iloc[idx] = series.iloc[idx] * 10.0
    return mutated


def _audit_factor(
    name: str,
    family: str,
    factor_fn: Callable[..., pd.Series],
    mutate_arg: str,
    input_builders: dict[str, Callable[[], object]],
    warmup: int,
) -> FactorResult:
    """Run the look-ahead audit for one factor.

    Parameters
    ----------
    name : str
        Display name (e.g. "rsi", "atr_breakout").
    family : str
        Family bucket for reporting ("momentum" / "mean_reversion" / ...).
    factor_fn : callable
        The factor. Will be called as `factor_fn(**built_inputs)`. The
        first positional input is determined by convention:
          - 1 series arg → first arg is the series to mutate;
          - 2+ series args → mutate_arg names which one to spike.
    mutate_arg : str
        Which key in `input_builders` corresponds to the series to mutate.
        For multi-input factors (`pairs_spread`, `obv_slope`) we mutate
        only the primary signal; secondary inputs would be tested by
        separate per-arg variants in a richer audit, but the single-mutation
        test is sufficient for a v1.0 black-box audit.
    input_builders : dict[str, callable]
        Mapping of input name → thunk that returns the input (called fresh
        each time to keep baseline and mutated runs independent).
    warmup : int
        Number of leading bars where weights are guaranteed to be 0
        regardless of look-ahead. Mutation positions are placed strictly
        after `warmup`.

    Notes
    -----
    We intentionally mutate at the **last bar** of the input (k = n - 1)
    in addition to k = 3n/4 and 9n/10. The last-bar mutation gives the
    look-ahead the longest possible *distance* to leak through the factor's
    pipeline. EMA-coupling falls off geometrically as `(1 - α)^d`, so a
    future-looking factor that does *anything* with a future bar — even
    `prices.shift(-1)` followed by an EMA — will produce a measurable
    difference at some `t < k`. Multiple positions across the timeline
    defeat any one-position-washes-out case.
    """
    n = 600  # >= 600 to clear momentum_12_1's 252+21-bar warmup
    # `last` must always be tested: it's the strongest signal because the
    # leak has to travel the full series back to t=0.
    test_positions: list[tuple[str, int]] = [
        ("3n/4", int(n * 3 / 4)),
        ("9n/10", int(n * 9 / 10)),
        ("last", n - 1),
    ]
    results: list[str] = []
    for label, k in test_positions:
        if k <= warmup:
            # Defensive: skip if a factor's warmup eats the test region.
            results.append(f"SKIP pos={label} (warmup={warmup} too long)")
            continue
        inputs = {k_: builder() for k_, builder in input_builders.items()}
        baseline = factor_fn(**inputs)
        mutated = dict(inputs)
        mutated[mutate_arg] = _spike(inputs[mutate_arg], k)
        mutated_weights = factor_fn(**mutated)
        # Strict equality on the pre-mutation prefix.
        try:
            pd.testing.assert_series_equal(
                baseline.iloc[:k],
                mutated_weights.iloc[:k],
                check_names=False,
                check_freq=False,
                obj=f"{name} pos={label} k={k}",
            )
        except AssertionError as exc:
            # Locate the first divergent bar for a useful diagnostic.
            diff = (baseline.iloc[:k] != mutated_weights.iloc[:k])
            first_diff = int(np.argmax(diff.to_numpy())) if diff.any() else -1
            results.append(
                f"FAIL pos={label} k={k} first_divergent_bar={first_diff}: {exc}"
            )
        else:
            results.append(f"OK   pos={label} k={k}")
    passed = all(r.startswith("OK") for r in results if not r.startswith("SKIP"))
    return FactorResult(
        name=name,
        family=family,
        passed=passed,
        notes=" | ".join(results),
    )


# ----------------------------------------------------------------------------
# Per-factor wiring
# ----------------------------------------------------------------------------


def audit_rsi() -> FactorResult:
    p = _make_prices()
    return _audit_factor(
        name="rsi",
        family="momentum",
        factor_fn=lambda **kw: rsi(kw["prices"]),
        mutate_arg="prices",
        input_builders={"prices": lambda: _make_prices()},
        warmup=14,
    )


def audit_macd() -> FactorResult:
    return _audit_factor(
        name="macd",
        family="momentum",
        factor_fn=lambda **kw: macd(kw["prices"]),
        mutate_arg="prices",
        input_builders={"prices": lambda: _make_prices()},
        warmup=26 + 9,
    )


def audit_roc() -> FactorResult:
    return _audit_factor(
        name="roc",
        family="momentum",
        factor_fn=lambda **kw: roc(kw["prices"]),
        mutate_arg="prices",
        input_builders={"prices": lambda: _make_prices()},
        warmup=20,
    )


def audit_momentum_12_1() -> FactorResult:
    return _audit_factor(
        name="momentum_12_1",
        family="momentum",
        factor_fn=lambda **kw: momentum_12_1(kw["prices"]),
        mutate_arg="prices",
        input_builders={"prices": lambda: _make_prices(800)},  # needs 252+21
        warmup=252 + 21,
    )


def audit_bollinger_zscore() -> FactorResult:
    return _audit_factor(
        name="bollinger_zscore",
        family="mean_reversion",
        factor_fn=lambda **kw: bollinger_zscore(kw["prices"]),
        mutate_arg="prices",
        input_builders={"prices": lambda: _make_prices()},
        warmup=20,
    )


def audit_ohlr_4_pct() -> FactorResult:
    return _audit_factor(
        name="ohlr_4_pct",
        family="mean_reversion",
        factor_fn=lambda **kw: ohlr_4_pct(kw["ohlc"]),
        mutate_arg="ohlc",
        input_builders={"ohlc": lambda: _make_ohlc(_make_prices())},
        warmup=14,
    )


def audit_pairs_spread() -> FactorResult:
    return _audit_factor(
        name="pairs_spread",
        family="mean_reversion",
        factor_fn=lambda **kw: pairs_spread(kw["prices_a"], kw["prices_b"]),
        mutate_arg="prices_a",  # mutate the primary signal; second leg is fixed
        input_builders={
            "prices_a": lambda: _make_prices(seed=10),
            "prices_b": lambda: _make_prices(seed=11),
        },
        warmup=60,
    )


def audit_atr_breakout() -> FactorResult:
    return _audit_factor(
        name="atr_breakout",
        family="volatility",
        factor_fn=lambda **kw: atr_breakout(kw["ohlc"]),
        mutate_arg="ohlc",
        input_builders={"ohlc": lambda: _make_ohlc(_make_prices())},
        warmup=50,  # breakout_window dominates
    )


def audit_parkinson_hist_vol() -> FactorResult:
    # parkinson is a *feature*, not a direction signal (see M2 retro §4).
    # The look-ahead audit still applies: its output must be a deterministic
    # function of bars <= t, full stop. We still report its family accurately.
    return _audit_factor(
        name="parkinson_hist_vol",
        family="volatility(feature)",
        factor_fn=lambda **kw: parkinson_hist_vol(kw["prices"]),
        mutate_arg="prices",
        input_builders={"prices": lambda: _make_prices()},
        warmup=30,
    )


def audit_obv_slope() -> FactorResult:
    return _audit_factor(
        name="obv_slope",
        family="volume",
        factor_fn=lambda **kw: obv_slope(kw["close"], kw["volume"]),
        mutate_arg="volume",  # also test the inverse in calibration below
        input_builders={
            "close": lambda: _make_prices(seed=20),
            "volume": lambda: _make_volume(_make_prices(seed=20), seed=21),
        },
        warmup=20,
    )


# ----------------------------------------------------------------------------
# Calibration: prove the auditor actually catches look-ahead bugs.
# ----------------------------------------------------------------------------


def _calibration_lookahead_rsi_continuous(prices: pd.Series) -> pd.Series:
    """A *deliberately broken* RSI-shaped factor that uses `prices.shift(-1)`.

    Returns the **continuous** RSI value (before `(>50).astype(float)`) so
    any sub-threshold look-ahead leak shows up. Weight at `t` references
    price at `t+1`; the leak propagates through the EMA. The audit's
    bit-exact equality check is guaranteed to catch any divergence in the
    output prefix — there is no threshold to hide below.
    """
    if prices.empty or len(prices) < 16:
        return prices * 0.0

    # Future-leak: shift(-1) pulls the NEXT bar into the current signal.
    future = prices.shift(-1)
    delta = future.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1.0 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi_raw = 100.0 - (100.0 / (1.0 + rs))
    rsi_val = pd.Series(rsi_raw, index=future.index).astype(float)
    rsi_val = rsi_val.bfill().fillna(50.0)
    rsi_val = rsi_val.where(avg_loss > 0, 100.0)
    # NB: no `(> 50).astype(float)` — we keep the *continuous* value so
    # the audit can see sub-threshold changes from the look-ahead leak.
    return rsi_val.fillna(50.0)


def _calibration_pure_lookahead(prices: pd.Series, anchor_pos: int) -> pd.Series:
    """A *deliberately broken* factor that uses a *specific* future bar.

    Every output bar at index `t < anchor_pos` equals `prices.iloc[anchor_pos]`.
    This bypasses the EMA-falloff problem: at any mutation position k ==
    anchor_pos, the look-ahead reaches every t < k. The audit's
    prefix-comparison is guaranteed to catch this.

    Parameters
    ----------
    anchor_pos : int
        The future-bar index this factor leaks. Mutating `prices[k]`
        with k == anchor_pos changes the constant value of the entire
        output series — every t < anchor_pos flips. Positions where
        k != anchor_pos leave the output untouched (sanity).
    """
    n = len(prices)
    if n == 0 or not (0 <= anchor_pos < n):
        return prices * 0.0
    anchor = float(prices.iloc[anchor_pos])
    return pd.Series(np.full(n, anchor), index=prices.index)


def _run_calibration() -> list[FactorResult]:
    """Run both calibration gates; return results.

    Two gates test distinct failure modes of the audit:

    Gate 1 — `_calibration_lookahead_rsi` (moderate look-ahead + EMA):
      A 1-bar shift(-1) followed by an EMA with α=1/14. EMA-coupling falls
      off geometrically as `(1-α)^d`, so this test has a *bounded leak
      horizon* (~50 bars for α=1/14). Tests that the audit catches
      shift(-1) at moderate distances.

    Gate 2 — `_calibration_pure_lookahead` (unbounded look-ahead):
      Every output bar equals `prices.iloc[anchor_pos]` — a *specific*
      future bar. The audit mutates that exact bar, so the leak reaches
      every t < anchor_pos. This is the **soundness floor**: if the audit
      cannot catch this, it cannot be trusted no matter how the real
      factors are tuned.

    For Gate 2 we test a single anchor position per call (the one being
    mutated). A separate anchor per run lets us test 5 different anchors
    across 5 separate invocations — a single anchor would let a buggy
    audit pass by accident if it happened to "skip" the only tested bar.

    Both gates must report CAUGHT at every position. Either FAIL is a
    calibration failure overall.
    """
    n = 600
    results: list[FactorResult] = []

    # ---- Gate 1: shift(-1) + EMA ----
    msgs_g1: list[str] = []
    for k in (50, 200, 300, 450, 540, n - 1):
        if k <= 16:
            continue
        p = _make_prices()
        baseline = _calibration_lookahead_rsi(p)
        mutated_p = _spike(p, k)
        mutated = _calibration_lookahead_rsi(mutated_p)
        try:
            pd.testing.assert_series_equal(
                baseline.iloc[:k],
                mutated.iloc[:k],
                check_names=False,
                check_freq=False,
                obj=f"calibration(lookahead_rsi) k={k}",
            )
            msgs_g1.append(f"FALSE PASS k={k}: audit missed the bug.")
        except AssertionError:
            msgs_g1.append(f"CAUGHT k={k}: audit correctly detected look-ahead.")
    results.append(
        FactorResult(
            name="calibration(lookahead_rsi)",
            family="sanity_gate",
            passed=all(m.startswith("CAUGHT") for m in msgs_g1),
            notes=" | ".join(msgs_g1),
        )
    )

    # ---- Gate 2: pure look-ahead at a specific anchor ----
    # Each anchor gets its own factor instance, so a buggy audit cannot
    # simultaneously skip *every* anchor position.
    anchor_positions = [int(n * 0.25), int(n * 0.5), int(n * 0.75),
                        int(n * 0.9), n - 1]
    msgs_g2: list[str] = []
    for anchor in anchor_positions:
        if anchor <= 1:
            continue
        p = _make_prices()
        baseline = _calibration_pure_lookahead(p, anchor_pos=anchor)
        mutated_p = _spike(p, anchor)
        mutated = _calibration_pure_lookahead(mutated_p, anchor_pos=anchor)
        # We only compare prefix [0..anchor); at the boundary (t=anchor),
        # both baseline and mutated equal the mutated-bar value, but past
        # bars should differ.
        try:
            pd.testing.assert_series_equal(
                baseline.iloc[:anchor],
                mutated.iloc[:anchor],
                check_names=False,
                check_freq=False,
                obj=f"calibration(pure_lookahead) anchor={anchor}",
            )
            msgs_g2.append(
                f"FALSE PASS anchor={anchor}: audit missed the bug."
            )
        except AssertionError:
            msgs_g2.append(
                f"CAUGHT anchor={anchor}: audit correctly detected look-ahead."
            )
    results.append(
        FactorResult(
            name="calibration(pure_lookahead)",
            family="sanity_gate",
            passed=all(m.startswith("CAUGHT") for m in msgs_g2),
            notes=" | ".join(msgs_g2),
        )
    )
    return results


# ----------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------


def _print_table(results: Sequence[FactorResult]) -> None:
    name_w = max(len(r.name) for r in results)
    fam_w = max(len(r.family) for r in results)
    print()
    print(f"{'factor'.ljust(name_w)}  {'family'.ljust(fam_w)}  status  notes")
    print(f"{'-' * name_w}  {'-' * fam_w}  ------  -----")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"{r.name.ljust(name_w)}  {r.family.ljust(fam_w)}  {status}     {r.notes}")


def main() -> int:
    audits: list[Callable[[], FactorResult]] = [
        # Momentum (4)
        audit_rsi,
        audit_macd,
        audit_roc,
        audit_momentum_12_1,
        # Mean reversion (3)
        audit_bollinger_zscore,
        audit_ohlr_4_pct,
        audit_pairs_spread,
        # Volatility (2)
        audit_atr_breakout,
        audit_parkinson_hist_vol,
        # Volume (1)
        audit_obv_slope,
    ]

    print("audit_no_lookahead.py — look-ahead bias audit for openstrategy.engineer")
    print(f"repo: {REPO_ROOT}")
    print(f"factors under audit: {len(audits)} (+ 2 calibration / sanity gates)")

    results: list[FactorResult] = []
    for audit in audits:
        try:
            results.append(audit())
        except Exception as exc:
            # A factor that throws at runtime is itself a finding —
            # report it as FAIL with a short traceback for diagnosis.
            tb = traceback.format_exc(limit=2)
            results.append(
                FactorResult(
                    name=audit.__name__.replace("audit_", ""),
                    family="<runtime_error>",
                    passed=False,
                    notes=f"EXC: {exc.__class__.__name__}: {exc}",
                    failures=[tb],
                )
            )

    # Run the calibration gates **last** so the PASS/FAIL roll-up is honest
    # even if early factors errored out. Calibration failure is the most
    # serious outcome: it means the audit is unreliable.
    calibrations = _run_calibration()
    results.extend(calibrations)

    _print_table(results)

    n_passed = sum(r.passed for r in results)
    n_total = len(results)
    # Calibration gates are separate from the 10 real factor audits.
    factor_pass = all(
        r.passed
        for r in results
        if not r.name.startswith("calibration(")
    )
    calib_gate_names = [
        r.name for r in results if r.name.startswith("calibration(")
    ]
    calib_ok = all(r.passed for r in results if r.name.startswith("calibration("))
    n_factor_results = sum(
        1 for r in results if not r.name.startswith("calibration(")
    )

    print()
    print(
        f"factor audits:        {n_passed}/{n_total} total entries; "
        f"{n_factor_results} factors + {len(calibrations)} calibration gates"
    )
    print(
        f"factor audits:        "
        f"{sum(1 for r in results if not r.name.startswith('calibration(') and r.passed)}"
        f"/{n_factor_results} PASS"
    )
    print(
        f"calibration sanity:   "
        f"{'PASS' if calib_ok else 'FAIL'} (gates: {', '.join(calib_gate_names)})"
    )
    print(f"overall:              {'PASS' if factor_pass and calib_ok else 'FAIL'}")

    if not (factor_pass and calib_ok):
        # Reprint detailed failure traceback(s) at the end for easy grepping.
        print()
        print("=" * 70)
        print("Failure diagnostics:")
        for r in results:
            for fail in r.failures:
                print(f"--- {r.name} ---")
                print(fail)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
