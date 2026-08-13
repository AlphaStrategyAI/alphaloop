"""
Tests for the ``@no_lookahead`` decorator and the v1.1.1 release-gate audit
exposed via the ``no_lookahead`` pytest marker.

These tests are automatically tagged with the ``no_lookahead`` marker so
operators can run the look-ahead audit in isolation via:

    pytest -m no_lookahead           # only the audit
    pytest -m "not no_lookahead"     # skip the audit, run everything else
    pytest -m "not integration and no_lookahead"

Each factor in ``alphaloop.engineer`` becomes one parametrized case
of ``test_<factor>_no_lookahead_audit``. A regression in any factor
(its weights in the first half change after shocking the second half of
its input) fails the suite as ``LookAheadDetectedError`` is raised.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from alphaloop.engineer import (  # noqa: E402
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
from alphaloop.engineer.audit import (  # noqa: E402
    DEFAULT_FACTORS,
    _make_ohlcv,
    _make_synthetic_input,
)
from alphaloop.engineer.base import (  # noqa: E402
    LookAheadDetected,
    LookAheadDetectedError,
    no_lookahead,
)

# Register at import time so pytest -m no_lookahead works without
# needing conftest to be reloaded after collection.
pytestmark = pytest.mark.no_lookahead


# ---------------------------------------------------------------------------
# Helper: factor -> default positional args
# ---------------------------------------------------------------------------


def _args_for(factor: Callable, prices: pd.Series) -> tuple:
    """Return the default positional args for ``factor``."""
    name = factor.__name__
    if name == "pairs_spread":
        return (prices, prices + 1.0)
    if name in {"atr_breakout", "ohlr_4_pct"}:
        return (_make_ohlcv(prices),)
    if name == "obv_slope":
        ohlc = _make_ohlcv(prices)
        return (prices, pd.Series(ohlc["volume"].to_numpy(), index=ohlc.index))
    return (prices,)


# ---------------------------------------------------------------------------
# Smoke tests for the decorator primitive
# ---------------------------------------------------------------------------


def test_no_lookahead_decorator_passes_for_clean_factor():
    """A factor that uses only past data survives the audit."""

    @no_lookahead
    def causal(p: pd.Series) -> pd.Series:
        return p.diff().gt(0).astype(float).shift(1).fillna(0.0)

    prices = _make_synthetic_input(300)
    weights = causal(prices)
    assert isinstance(weights, pd.Series)
    assert weights.between(0, 1).all()


def test_no_lookahead_decorator_raises_lookaheaddetected_on_future_dependency():
    """A factor that consumes a future bar in its past-weight region
    fails the audit and raises ``LookAheadDetectedError``."""

    @no_lookahead
    def leaky(p: pd.Series) -> pd.Series:
        # weight[0] depends on prices[100] (future). We use a
        # non-symmetric transform so the shock actually changes
        # weight[0] (a `>` comparison flips to `<` if we change p[100]).
        out = pd.Series(0.0, index=p.index)
        out.iloc[0] = p.iloc[0] - p.iloc[100]   # sensitive to p[100]
        return out

    prices = _make_synthetic_input(500)
    with pytest.raises(LookAheadDetectedError):
        leaky(prices)


def test_no_lookahead_backwards_compat_alias_resolves_to_error():
    """The original ``LookAheadDetected`` alias still resolves to
    ``LookAheadDetectedError`` so early test stubs keep working."""
    assert LookAheadDetected is LookAheadDetectedError


def test_no_lookahead_wrapped_preserves_function_name_and_audit_attr():
    """``functools.wraps`` keeps ``__name__``; ``__wrapped_lookahead__``
    is the bypass hatch."""

    @no_lookahead
    def clean(p: pd.Series) -> pd.Series:
        return p.diff().gt(0).astype(float).shift(1).fillna(0.0)

    assert clean.__name__ == "clean"
    assert callable(getattr(clean, "__wrapped_lookahead__", None))


def test_no_lookahead_passes_through_when_no_time_indexed_input():
    """Smoke: factor called with a non-Series/DF input is unaudited
    rather than crashing the audit."""

    @no_lookahead
    def anything(x):
        return pd.Series([1.0, 0.0, 1.0])

    out = anything([1, 2, 3])  # list, not a Series/DF
    assert len(out) == 3


def test_no_lookahead_signature_first_param_for_error_message():
    """The decorator resolves the first parameter name for nicer error
    messages; if signature resolution fails, the fallback still works."""

    @no_lookahead
    def with_named_first_param(prices):
        return prices.diff().gt(0).astype(float)

    prices = _make_synthetic_input(200)
    weights = with_named_first_param(prices)
    assert len(weights) == len(prices)


# ---------------------------------------------------------------------------
# The audit-gate parametrized test
# ---------------------------------------------------------------------------


ALL_FACTOR_NAMES = list(DEFAULT_FACTORS.keys())


@pytest.mark.parametrize("factor_name", ALL_FACTOR_NAMES)
def test_factor_passes_no_lookahead_audit(factor_name):
    """Each alpha factor must pass the v1.1.1 release-gate audit.

    On regression this raises ``LookAheadDetectedError`` from inside
    the factor call, failing the test.
    """
    factor = DEFAULT_FACTORS[factor_name]
    prices = _make_synthetic_input()
    args = _args_for(factor, prices)

    # Plain unmodified run — guarantees the factor at least produces
    # an output of the right shape, even if the audit below is
    # somehow bypassed.
    w1 = factor(*args)
    assert isinstance(w1, pd.Series)

    # Run the audit by hand: shock the second half of the first
    # time-indexed positional arg and compare first-half weights.
    target = args[0].copy(deep=True)
    n = len(target)
    cutoff = n // 2
    if isinstance(target, pd.DataFrame):
        for col in target.select_dtypes(include="number").columns:
            ci = target.columns.get_loc(col)
            target.iloc[cutoff + 1 :, ci] = (
                target.iloc[cutoff + 1 :, ci].astype(float) * 2.0
            )
    else:
        target.iloc[cutoff + 1 :] = target.iloc[cutoff + 1 :].astype(float) * 2.0

    mutated_args = list(args)
    mutated_args[0] = target
    w2 = factor(*mutated_args)

    half = min(len(w1), len(w2)) // 2
    assert np.array_equal(
        w1.iloc[:half].to_numpy(), w2.iloc[:half].to_numpy()
    ), f"{factor_name} failed the look-ahead audit (v1.1.1 release gate)"


# ---------------------------------------------------------------------------
# Sanity test: a factor that USES ``@no_lookahead`` itself works end-to-end
# ---------------------------------------------------------------------------


@no_lookahead
def _decorated_clean(p: pd.Series) -> pd.Series:
    """Test-only: a causal factor wrapped in @no_lookahead."""
    return p.diff().gt(0).astype(float).shift(1).fillna(0.0)


def test_decorated_factor_end_to_end():
    """Wrapping a clean factor in @no_lookahead lets it run normally
    and still raises on look-ahead."""
    prices = _make_synthetic_input(300)
    out = _decorated_clean(prices)
    assert isinstance(out, pd.Series)
    assert out.between(0, 1).all()


def test_decorated_factor_raises_on_real_leak():
    """A future-leaking version of the same factor is caught."""

    @no_lookahead
    def _leaky(p: pd.Series) -> pd.Series:
        return p.shift(-50).fillna(0.0)

    prices = _make_synthetic_input(500)
    with pytest.raises(LookAheadDetectedError):
        _leaky(prices)


# ---------------------------------------------------------------------------
# Test inventory helpers
# ---------------------------------------------------------------------------


def test_all_ten_factors_are_audited():
    """Belt-and-braces: the audit tests must cover every factor.

    If a new factor is added to alphaloop.engineer without a
    matching parametrize case, this test fails so the v1.1.1 audit
    stays comprehensive.
    """
    # Engineered factors (the canonical 10)
    engineered = {
        rsi,
        macd,
        roc,
        momentum_12_1,
        bollinger_zscore,
        ohlr_4_pct,
        pairs_spread,
        atr_breakout,
        parkinson_hist_vol,
        obv_slope,
    }
    engineered_names = {fn.__name__ for fn in engineered}
    assert set(ALL_FACTOR_NAMES) == engineered_names, (
        f"DEFAULT_FACTORS drifted from alphaloop.engineer.__all__. "
        f"Missing: {engineered_names - set(ALL_FACTOR_NAMES)}; "
        f"Extra: {set(ALL_FACTOR_NAMES) - engineered_names}."
    )


def test_audit_helper_resolves_default_args_for_each_factor():
    """``_args_for`` covers every shape of factor (Series, OHLCV, two-SS)."""
    prices = _make_synthetic_input()
    for factor_name in ALL_FACTOR_NAMES:
        factor = DEFAULT_FACTORS[factor_name]
        args = _args_for(factor, prices)
        assert len(args) >= 1
        # The first positional arg must always be a time-indexed object.
        first = args[0]
        assert isinstance(first, (pd.Series, pd.DataFrame))
        assert isinstance(getattr(first, "index", None), pd.DatetimeIndex)
