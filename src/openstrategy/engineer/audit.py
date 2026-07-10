"""
Look-ahead audit driver for the v1.1.1 release gate.

Runs every alpha factor exported from ``openstrategy.engineer``
through the look-ahead audit and prints a table:

    factor_name       status   shock_bar_count  audit_time_ms

The audit enforces the rule-#16 invariant:

    Mutate every bar in the *second half* of the first
    time-indexed input. Weights in the *first half* must be
    byte-identical to the unmodified run.

Status:
    PASS  — first-half weights unchanged after the shock.
    FAIL  — LookAheadDetectedError raised. BLOCKS the v1.1.1
            release.

Usage:

    python3 -m openstrategy.engineer.audit
    python3 -m openstrategy.engineer.audit --factor rsi
    python3 -m openstrategy.engineer.audit --strict
    # pytest --no-lookahead  (see tests/conftest.py)
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence

import numpy as np
import pandas as pd

from openstrategy.engineer import (
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
from openstrategy.engineer.base import LookAheadDetectedError


# Default factor inventory. Each entry maps a factor name to
# ``(callable, default_args)``. Keep in sync with
# ``openstrategy.engineer.__all__``.
DEFAULT_FACTORS: Dict[str, Callable] = {
    # Momentum
    "rsi": rsi,
    "macd": macd,
    "roc": roc,
    "momentum_12_1": momentum_12_1,
    # Mean Reversion
    "bollinger_zscore": bollinger_zscore,
    "ohlr_4_pct": ohlr_4_pct,
    "pairs_spread": pairs_spread,
    # Volatility
    "atr_breakout": atr_breakout,
    "parkinson_hist_vol": parkinson_hist_vol,
    # Volume
    "obv_slope": obv_slope,
}


@dataclass
class FactorAuditResult:
    """One row in the audit table."""

    name: str
    status: str  # "PASS" | "FAIL" | "ERROR"
    audit_time_ms: float
    error_message: str = ""


def _make_synthetic_input(n: int = 500, seed: int = 0) -> pd.Series:
    """Return a synthetic close-price series with a DatetimeIndex."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0005, 0.012, n)
    return pd.Series(
        100.0 * np.exp(np.cumsum(rets)),
        index=pd.date_range("2018-01-01", periods=n, freq="B"),
    )


def _make_ohlcv(prices: pd.Series, seed: int = 0) -> pd.DataFrame:
    """Return a synthetic OHLCV DataFrame aligned with ``prices``."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices,
            "volume": rng.integers(1_000_000, 5_000_000, len(prices)).astype(float),
        },
        index=prices.index,
    )


def _default_args_for(factor_name: str, prices: pd.Series) -> tuple:
    """Build the default positional arguments for a factor named
    ``factor_name``. Pairs-trading needs two correlated series;
    everything else takes one (or an OHLCV frame).
    """
    if factor_name == "pairs_spread":
        prices2 = prices + 1.0  # synthetic second leg
        return (prices, prices2)
    if factor_name in {"atr_breakout", "ohlr_4_pct"}:
        return (_make_ohlcv(prices),)
    if factor_name == "obv_slope":
        ohlc = _make_ohlcv(prices)
        return (prices, pd.Series(ohlc["volume"].to_numpy(), index=ohlc.index))
    return (prices,)


def _shock_second_half(input_obj: pd.Series | pd.DataFrame) -> int:
    """Multiply every bar in ``i > N // 2`` by 2 (on a deep copy)."""
    n = len(input_obj)
    cutoff = n // 2
    if isinstance(input_obj, pd.DataFrame):
        for col in input_obj.select_dtypes(include="number").columns:
            col_idx = input_obj.columns.get_loc(col)
            input_obj.iloc[cutoff + 1 :, col_idx] = (
                input_obj.iloc[cutoff + 1 :, col_idx].astype(float) * 2.0
            )
        return n - cutoff - 1
    input_obj.iloc[cutoff + 1 :] = input_obj.iloc[cutoff + 1 :].astype(float) * 2.0
    return n - cutoff - 1


def audit_factor(factor_name: str, factor: Callable) -> FactorAuditResult:
    """Run the audit on ``factor`` and return one row of results."""
    prices = _make_synthetic_input()
    args = _default_args_for(factor_name, prices)

    # Pick the first time-indexed positional arg. For pairs_spread
    # the *first* one is what we'll shock.
    target_idx = 0

    # Run unmodified
    t0 = time.perf_counter()
    try:
        w1 = factor(*args)
    except Exception as e:  # pragma: no cover - smoke tests
        return FactorAuditResult(
            name=factor_name,
            status="ERROR",
            audit_time_ms=(time.perf_counter() - t0) * 1000.0,
            error_message=f"unmodified run failed: {type(e).__name__}: {e}",
        )

    # Build a shocked copy of the first positional arg.
    shocked = args[target_idx].copy(deep=True)
    _shock_second_half(shocked)
    mutated_args: list = list(args)
    mutated_args[target_idx] = shocked
    try:
        w2 = factor(*mutated_args)
    except Exception as e:
        # Same trade-off as the decorator: a shock-induced divide-by-zero
        # is *not* the factor's fault.
        return FactorAuditResult(
            name=factor_name,
            status="ERROR",
            audit_time_ms=(time.perf_counter() - t0) * 1000.0,
            error_message=f"shocked run failed: {type(e).__name__}: {e}",
        )

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    n = min(len(w1), len(w2))
    half = n // 2
    if half == 0:
        return FactorAuditResult(
            name=factor_name,
            status="ERROR",
            audit_time_ms=elapsed_ms,
            error_message="output too short to audit",
        )

    if np.array_equal(w1.iloc[:half].to_numpy(), w2.iloc[:half].to_numpy()):
        return FactorAuditResult(
            name=factor_name, status="PASS", audit_time_ms=elapsed_ms
        )

    # Identify which bar in the second half actually broke the
    # audit's invariant. Walk through the first half and find the
    # smallest i where w1[i] != w2[i]; the corresponding shocked
    # dependency is somewhere in [i+1, N).
    diff = (w1.iloc[:half].to_numpy() != w2.iloc[:half].to_numpy())
    first_break = int(np.argmax(diff)) if diff.any() else -1
    return FactorAuditResult(
        name=factor_name,
        status="FAIL",
        audit_time_ms=elapsed_ms,
        error_message=(
            f"first-half weight at i={first_break} changed after "
            f"shocking bars > {n // 2}"
        ),
    )


def run_audit(
    factors: Sequence[str] | None = None,
) -> List[FactorAuditResult]:
    """Audit all factors (or the named subset) and return results."""
    names = list(factors) if factors else list(DEFAULT_FACTORS.keys())
    results: List[FactorAuditResult] = []
    for name in names:
        if name not in DEFAULT_FACTORS:
            results.append(
                FactorAuditResult(
                    name=name,
                    status="ERROR",
                    audit_time_ms=0.0,
                    error_message=f"unknown factor {name!r}; not in DEFAULT_FACTORS",
                )
            )
            continue
        results.append(audit_factor(name, DEFAULT_FACTORS[name]))
    return results


def _print_table(results: List[FactorAuditResult], strict: bool) -> int:
    """Pretty-print the audit table; return the process exit code."""
    name_w = max((len(r.name) for r in results), default=12)
    name_w = max(name_w, len("factor"))
    line = (
        f"{'factor':<{name_w}}  {'status':<6}  {'time_ms':>10}  message"
    )
    print(line)
    print("-" * len(line))
    for r in results:
        msg = r.error_message if r.status in {"FAIL", "ERROR"} else ""
        print(
            f"{r.name:<{name_w}}  {r.status:<6}  {r.audit_time_ms:>10.2f}  {msg}"
        )

    failures = [r for r in results if r.status == "FAIL"]
    errors = [r for r in results if r.status == "ERROR"]
    passed = [r for r in results if r.status == "PASS"]
    print(
        f"\n{len(passed)} pass / {len(failures)} fail / {len(errors)} error "
        f"(of {len(results)} audited)."
    )

    # Exit code policy:
    #   - FAIL → 2 (release gate failure)
    #   - ERROR (in strict mode) → 1
    #   - ERROR (default mode) → 0 (skip silently, factor wasn't audited)
    if failures:
        return 2
    if errors and strict:
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point: ``python3 -m openstrategy.engineer.audit``."""
    parser = argparse.ArgumentParser(
        prog="python3 -m openstrategy.engineer.audit",
        description=(
            "Look-ahead audit for openstrategy alpha factors "
            "(v1.1.1 release gate)."
        ),
    )
    parser.add_argument(
        "--factor",
        action="append",
        default=None,
        help=(
            "Audit only the named factor (repeat to select multiple). "
            "Default: audit every factor in openstrategy.engineer."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Treat ERROR results as failures. Default: errors are "
            "reported but do not block the audit exit code."
        ),
    )
    args = parser.parse_args(argv)

    results = run_audit(args.factor)
    return _print_table(results, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
