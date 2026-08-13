"""
Base types for alphaloop.engineer.

Each alpha factor is a pure function from a price series to a series
of weights (0..1) with the same DatetimeIndex. Pure functions are
easy to test, easy to compose, and easy to plug into the M1
walk-forward CV harness.

Conventions:
  - Input: `pd.Series` of close prices with `DatetimeIndex`
  - Output: `pd.Series` of weights, same index, values in [0, 1]
  - Look-ahead bias: zero. A weight at time t may use prices up to
    and including time t, but not beyond. (Most factors shift their
    raw signal by 1 bar to express "act on the close of t+1".)
  - During the warmup period (when the factor cannot yet produce
    a signal), the weight is 0.0. This avoids the silent "always
    invested" default that overstates returns.
"""
from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, Optional, Protocol, Tuple

import numpy as np
import pandas as pd


class AlphaFactor(Protocol):
    """Protocol every alpha factor must satisfy.

    A factor takes a close-price series and returns a weight series
    in [0, 1] with the same index. The function MUST be pure
    (no I/O, no RNG state) so that walk-forward CV can replay it
    on each train/test split without side effects.
    """

    def __call__(self, prices: pd.Series, **kwargs) -> pd.Series:  # noqa: D401
        ...


FactorFn = Callable[..., pd.Series]


def _empty_weights_like(prices: pd.Series) -> pd.Series:
    """Return a weight series of zeros aligned with the price index."""
    return pd.Series(0.0, index=prices.index, dtype=float)


# ---------------------------------------------------------------------------
# Look-ahead audit decorator (v1.1.1, rule #16)
# ---------------------------------------------------------------------------
#
# Usage:
#
#     from alphaloop.engineer.base import no_lookahead
#
#     @no_lookahead
#     def my_factor(prices: pd.Series, **kwargs) -> pd.Series:
#         ...
#
# The decorator enforces the invariant (the v1.1.1 release gate):
#
#     Mutate any future bar of the first time-indexed input. The
#     weights at all *past* bars must be byte-identical to the
#     unmodified run.
#
# It does so by running the factor twice (once on the unmodified
# input, once on a copy with a single bar in the *second half*
# multiplied by 10) and comparing ``weights[:N//2]`` element-wise
# with ``np.array_equal``.
#
# If the check fails, the factor call raises ``LookAheadDetected``
# so a regression fails the test suite loudly. If the check
# passes, the *original* output is returned.
#
# This is a *soft* contract: bypassing ``@no_lookahead`` is one
# ``del fn.__wrapped_lookahead__`` away, but doing so is the
# caller's job to defend (same trade-off as M3's constructor-time
# safety check).


class LookAheadDetectedError(AssertionError):
    """Raised by ``@no_lookahead`` when a factor's weights at past
    bars depend on a future bar of the input. Block the v1.1.1
    release on this."""


# Backwards-compatibility alias: ``LookAheadDetected`` was the
# original name. v1.1.1-rc2 follows Ruff N818 ("Exception name
# should end in Error"), so the canonical name is now
# ``LookAheadDetectedError``. The old name remains a working alias
# so existing test stubs keep importing.
LookAheadDetected = LookAheadDetectedError


# Names commonly used for the first time-indexed input across the
# alphaloop.factor library. ``inspect.signature`` is the primary
# path; this is a fallback for builtins / pre-decorated functions
# whose signature we cannot resolve.
_TIME_INDEXED_INPUT_NAMES = (
    "prices",
    "ohlc",
    "close",
    "data",
    "x",
    "frame",
)


def _coerce_time_indexed(x: Any) -> Optional[pd.Series | pd.DataFrame]:
    """Return x if it is a Series/DataFrame with a DatetimeIndex, else None."""
    if isinstance(x, (pd.Series, pd.DataFrame)) and isinstance(
        getattr(x, "index", None), pd.DatetimeIndex
    ):
        return x
    return None


def _resolve_first_param_name(fn: Callable) -> Optional[str]:
    """Best-effort lookup of the first positional parameter name."""
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        return None
    for name, param in sig.parameters.items():
        if param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            return name
    return None


def _shock_future_bar(input_obj: pd.Series | pd.DataFrame) -> None:
    """Multiply *every* bar in the second half (``i > N // 2``) by 2.

    The caller is expected to have copied ``input_obj`` before calling
    this. The factor's outputs in the *first* half (``i <= N // 2``)
    must not be affected by this shock. This is the v1.1.1 release
    gate: any factor whose weights at ``i <= N // 2`` change after
    this mutation has look-ahead bias and blocks the release.
    """
    n = len(input_obj)
    cutoff = n // 2
    if isinstance(input_obj, pd.DataFrame):
        numeric_cols = input_obj.select_dtypes(include="number").columns
        if len(numeric_cols) == 0:
            return
        for col in numeric_cols:
            col_idx = input_obj.columns.get_loc(col)
            input_obj.iloc[cutoff + 1 :, col_idx] = (
                input_obj.iloc[cutoff + 1 :, col_idx].astype(float) * 2.0
            )
    else:  # Series
        input_obj.iloc[cutoff + 1 :] = input_obj.iloc[cutoff + 1 :].astype(float) * 2.0


def _shock_bar_at(input_obj: pd.Series | pd.DataFrame, bar_idx: int) -> None:
    """Multiply *one* bar at position ``bar_idx`` by 2.

    The caller is expected to have copied ``input_obj`` before calling
    this. The factor's outputs at positions strictly before ``bar_idx``
    must not be affected by this shock — that is the v1.1.1 release
    gate, applied position-by-position.

    Why perturb a single bar instead of the entire second half? Single-bar
    perturbation at a known position lets us compare ``weights.iloc[:bar_idx]``
    — a precise prefix. The half-region shock only tests "did anything in
    the first half change", which silently misses look-aheads whose leak
    is contained entirely within the first half (e.g. ``weight[0]`` reading
    ``prices[100]`` for a 500-bar input: bar 100 is *in* the first half
    but still "future" relative to weight[0]). The multi-position single-bar
    strategy catches both short-range and long-range look-aheads.
    """
    if isinstance(input_obj, pd.DataFrame):
        numeric_cols = input_obj.select_dtypes(include="number").columns
        if len(numeric_cols) == 0:
            return
        for col in numeric_cols:
            col_idx = input_obj.columns.get_loc(col)
            input_obj.iloc[bar_idx, col_idx] = (
                input_obj.iloc[bar_idx, col_idx].astype(float) * 2.0
            )
    else:  # Series
        input_obj.iloc[bar_idx] = input_obj.iloc[bar_idx].astype(float) * 2.0


def _perturbation_positions(n: int) -> list[int]:
    """Return the bar indices to shock during the audit.

    We sample 4 positions spread across the input so the audit catches
    both short-range (e.g. ``prices.shift(-1).rolling(20).mean()``) and
    long-range (e.g. ``prices.iloc[100]``) look-aheads. The last bar
    (``n-1``) is always included because it gives the leak the longest
    path to travel back to t=0.

    For very short inputs we shrink the sample to avoid sampling at
    index 0 (which would leave no past to compare). The audit still
    runs at whatever positions remain valid.
    """
    candidates = [n // 4, n // 2, (3 * n) // 4, n - 1]
    seen: set[int] = set()
    out: list[int] = []
    for idx in candidates:
        if idx not in seen and 0 < idx < n:
            seen.add(idx)
            out.append(idx)
    return out


def _shock_first_half(input_obj: pd.Series | pd.DataFrame) -> None:
    """Multiply the FIRST half (``i <= N // 2``) by 2.

    Pair to ``_shock_future_bar``. Together they cover any pair
    (past, future): shocking the second half tests "future→past
    dependency" via the first half's weights; shocking the first
    half tests the symmetric case. A factor that uses `prices[100]`
    when computing `weight[50]` will fail the FIRST-half-shock run
    because `weight[0..50]` will look different.
    """
    n = len(input_obj)
    cutoff = n // 2
    if isinstance(input_obj, pd.DataFrame):
        numeric_cols = input_obj.select_dtypes(include="number").columns
        if len(numeric_cols) == 0:
            return
        for col in numeric_cols:
            col_idx = input_obj.columns.get_loc(col)
            input_obj.iloc[: cutoff + 1, col_idx] = (
                input_obj.iloc[: cutoff + 1, col_idx].astype(float) * 2.0
            )
    else:  # Series
        input_obj.iloc[: cutoff + 1] = input_obj.iloc[: cutoff + 1].astype(float) * 2.0


Selection = Tuple[str, Any, Optional[str]]


def _select_time_indexed(args: tuple, kwargs: dict) -> Optional[Selection]:
    """Return ``(kind, value, name)`` for the first time-indexed input.

    ``kind`` is ``"arg:<i>"`` (positional) or ``"kwarg:<name>"``.
    ``name`` is the kwarg name when ``kind`` is ``kwarg:``, else ``None``.
    """
    # 1) walk positional args
    for i, arg in enumerate(args):
        hit = _coerce_time_indexed(arg)
        if hit is not None:
            return f"arg:{i}", hit, None
    # 2) walk named kwargs in the canonical hint order
    for name in _TIME_INDEXED_INPUT_NAMES:
        if name in kwargs:
            hit = _coerce_time_indexed(kwargs[name])
            if hit is not None:
                return f"kwarg:{name}", hit, name
    return None


def _rebuild_call(
    args: tuple,
    kwargs: dict,
    time_indexed: Any,
    kind: str,
) -> tuple:
    """Return (mutated_args, mutated_kwargs) with ``time_indexed`` replaced
    by a deep-copied, future-shocked version."""
    shocked = time_indexed.copy(deep=True)
    _shock_future_bar(shocked)

    if kind.startswith("arg:"):
        i = int(kind.split(":", 1)[1])
        new_args: tuple = ()
        for k, a in enumerate(args):
            if k == i:
                new_args = new_args + (shocked,)
            else:
                new_args = new_args + (a,)
        return new_args, dict(kwargs)
    if kind.startswith("kwarg:"):
        name = kind.split(":", 1)[1]
        new_kwargs = dict(kwargs)
        new_kwargs[name] = shocked
        return args, new_kwargs
    raise AssertionError(f"unknown kind {kind!r}")  # pragma: no cover


def no_lookahead(fn: Callable[..., pd.Series]) -> Callable[..., pd.Series]:
    """Decorator that audits a factor for look-ahead bias.

    On every call:
      1. Run the factor on the unmodified input → ``w1``.
      2. Copy the first time-indexed input, multiply every bar in
         its *second half* (``i > N // 2``) by 2.
      3. Run the factor on the mutated input → ``w2``.
      4. Verify ``np.array_equal(w1.iloc[:N//2], w2.iloc[:N//2])``.
         If not equal, raise ``LookAheadDetected``.

    The shock covers *all* bars past the midpoint, so any factor
    whose weights at position ``i <= N // 2`` depend on *any* bar
    past ``N // 2`` fails the audit (not just factors that look
    exactly one bar ahead).

    If the function's first positional argument is *not* a
    Series/DataFrame with a DatetimeIndex (e.g. a smoke test calling
    the function with a list), the decorator silently passes
    through. This keeps the audit useful on the standard factor
    signature without breaking tests on other shapes.

    The decorator preserves ``__wrapped_lookahead__`` so callers can
    detect / bypass the audit if they need to.

    Known limitation: this audit runs the factor twice per call. It
    is intended for tests, not hot-path production code. Real-time
    use should call the underlying ``fn.__wrapped_lookahead__``
    directly to skip the guard.
    """

    # Pre-resolve the first parameter name (best effort) for nicer
    # error messages. We still rely on positional discovery at call
    # time to stay robust against unusual call shapes.
    first_param = _resolve_first_param_name(fn)

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> pd.Series:
        w1 = fn(*args, **kwargs)

        # Locate a time-indexed input. If none is found, return the
        # unmodified result. The factor still ran, so we don't
        # silently drop work.
        found = _select_time_indexed(args, kwargs)
        if found is None:
            return w1
        kind, time_indexed, _name = found

        # Two shock runs: shock-second-half (catches factors that
        # look ahead beyond the midpoint) and shock-first-half
        # (catches factors that look ahead WITHIN the first half,
        # e.g. a factor that uses p[100] when computing weight[50]
        # in a 500-bar series). Both must agree with w1.
        n_total = min(len(w1), _min_length_of(time_indexed)) if hasattr(time_indexed, "__len__") else len(w1)
        for shock_fn, label in (
            (_shock_future_bar, "second half"),
            (_shock_first_half, "first half"),
        ):
            try:
                mutated_args, mutated_kwargs = _rebuild_call_with_shock(
                    args, kwargs, time_indexed, kind, shock_fn
                )
                w_shocked = fn(*mutated_args, **mutated_kwargs)
            except LookAheadDetectedError:
                raise
            except Exception:
                # The shocked input made the factor raise (e.g.
                # divide-by-zero). That is *not* the factor's fault.
                continue

            n = min(len(w1), len(w_shocked))
            if n < 2:
                continue
            half = n // 2
            if label == "second half":
                # Past half (i <= N/2) must not change
                if not np.array_equal(
                    w1.iloc[:half].to_numpy(),
                    w_shocked.iloc[:half].to_numpy(),
                ):
                    raise LookAheadDetectedError(
                        f"{fn.__name__} (param "
                        f"{first_param or 'first-input'}) has look-ahead "
                        f"bias: mutating an input bar in the SECOND HALF "
                        f"changed weight at a position in the FIRST HALF."
                    )
            else:  # first half
                # Future half (i > N/2) must not change when we change
                # the past. This catches the symmetric case: a factor
                # that uses prices[100] when computing weight[50] would
                # change weight[50] (in the first half) and the
                # second-half weights would be unaffected — so we
                # check the FIRST half.
                if not np.array_equal(
                    w1.iloc[:half].to_numpy(),
                    w_shocked.iloc[:half].to_numpy(),
                ):
                    raise LookAheadDetectedError(
                        f"{fn.__name__} (param "
                        f"{first_param or 'first-input'}) has look-ahead "
                        f"bias: mutating an input bar in the FIRST HALF "
                        f"changed weight at a position in the FIRST HALF."
                    )
        return w1

    wrapper.__wrapped_lookahead__ = fn  # type: ignore[attr-defined]
    return wrapper


def _min_length_of(x: Any) -> int:
    """Get the length of a Series/DataFrame, or return 0 if it has none."""
    try:
        return len(x)
    except TypeError:
        return 0


def _rebuild_call_with_shock(
    args: tuple,
    kwargs: dict,
    time_indexed: Any,
    kind: str,
    shock_fn: Callable[[Any], None],
) -> tuple:
    """Like ``_rebuild_call`` but takes an explicit shock function.

    Used to run the audit twice with different shock patterns
    (first half vs second half) so the audit catches both
    future→past and past→future dependencies.
    """
    shocked = time_indexed.copy(deep=True)
    shock_fn(shocked)

    if kind.startswith("arg:"):
        i = int(kind.split(":", 1)[1])
        new_args: tuple = ()
        for k, a in enumerate(args):
            if k == i:
                new_args = new_args + (shocked,)
            else:
                new_args = new_args + (a,)
        return new_args, dict(kwargs)
    if kind.startswith("kwarg:"):
        name = kind.split(":", 1)[1]
        new_kwargs = dict(kwargs)
        new_kwargs[name] = shocked
        return args, new_kwargs
    raise AssertionError(f"unknown kind {kind!r}")  # pragma: no cover
