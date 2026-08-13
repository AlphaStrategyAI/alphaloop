"""
Deflated Sharpe Ratio (DSR).

The DSR adjusts an observed Sharpe ratio for the number of trials
performed. With many strategy variants, the highest observed Sharpe
is almost certainly an over-estimate of the true (out-of-sample)
Sharpe. This module computes:

  - DSR (Bailey & Lopez de Prado, 2014): probability that the true
    Sharpe exceeds a threshold, after deflating for multiple testing.
  - Expected maximum Sharpe under the null (E[max SR | H0]) used as
    the benchmark.

Reference:
    Bailey, D. H., & Lopez de Prado, M. (2014). "The Deflated Sharpe
    Ratio: Correcting for Selection Bias, Backtest Overfitting, and
    Non-Normality." Journal of Portfolio Management, 40(5), 94-107.

No scipy dependency — uses math.erf for the standard normal CDF and a
Newton-iteration fallback for the inverse CDF. This keeps the
diagnostic package light (no transitive build deps).

Usage:
    from alphaloop.diagnostic import deflated_sharpe

    result = deflated_sharpe(
        observed_sharpe=1.8,
        n_trials=20,
        returns=series_of_strategy_returns,  # optional, for higher moments
    )
    print(result.summary())
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Union

import numpy as np
import pandas as pd


# --- Standard normal helpers (avoid scipy dependency) ---


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using math.erf (max error ~1.5e-7)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float, tol: float = 1e-9, max_iter: int = 100) -> float:
    """Standard normal inverse CDF via Beasley-Springer-Moro / Newton.

    For p in (0, 1); raises ValueError for p outside (0, 1).
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0, 1), got {p}")
    if p < 0.5:
        return -_norm_ppf(1.0 - p, tol=tol, max_iter=max_iter)

    # Beasley-Springer-Moro rational approximation for the upper half
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e02,
        -1.328068155288572e03,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]

    p_low = 0.02425
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (
            ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
        ) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    if p <= 1.0 - p_low:
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        ) / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(
        ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
    ) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)


# --- DSR core ---


@dataclass
class DeflatedSharpeResult:
    """Result of a Deflated Sharpe Ratio computation."""

    observed_sharpe: float
    n_trials: int
    expected_max_sharpe: float
    dsr: float  # probability that true SR > 0 (deflated)
    p_value: float  # 1 - dsr
    passes: bool  # dsr >= confidence

    def summary(self) -> str:
        verdict = "PASS" if self.passes else "FAIL"
        return (
            f"DSR verdict: {verdict}\n"
            f"  Observed Sharpe:  {self.observed_sharpe:.3f}\n"
            f"  N trials:         {self.n_trials}\n"
            f"  Expected max SR:  {self.expected_max_sharpe:.3f}\n"
            f"  DSR (P[true>0]):  {self.dsr:.3f}\n"
            f"  P-value:          {self.p_value:.3f}"
        )


def _higher_moments(returns: "Union[pd.Series, np.ndarray]") -> tuple[float, float]:
    """Return (skewness, excess kurtosis) of returns."""
    if isinstance(returns, pd.Series):
        arr = returns.to_numpy()
    else:
        arr = np.asarray(returns, dtype=float)
    n = len(arr)
    if n < 4:
        return 0.0, 0.0
    mean = arr.mean()
    std = arr.std(ddof=1)
    if std == 0:
        return 0.0, 0.0
    centered = (arr - mean) / std
    skew = float(np.mean(centered**3))
    kurt = float(np.mean(centered**4)) - 3.0
    return skew, kurt


def expected_max_sharpe(
    n_trials: int,
    skewness: float = 0.0,
    excess_kurtosis: float = 0.0,
    n_obs_per_trial: int = 252,
) -> float:
    """Expected maximum Sharpe under H0 (no skill) across n_trials.

    Closed-form approximation from Bailey & Lopez de Prado (2014),
    equation (4). For a normal (or near-normal) SR estimator under H0,
    the expected max of n_trials i.i.d. draws is:
        E[max] ~ (1 - gamma) * z_alpha + gamma * z_(alpha - 1/(n*e))
    where z_alpha = Phi^{-1}(1 - 1/n) and gamma is the Euler-Mascheroni
    constant. We scale by sqrt(Var(SR)).

    Note: the simplified form here uses Var(SR) ~ 1/N under H0 with a
    small kurtosis correction. For full Bailey & Lopez de Prado eq (2),
    one would also use the observed SR magnitude, but under H0 SR ~ 0.
    """
    if n_trials < 1:
        raise ValueError(f"n_trials must be >= 1, got {n_trials}")
    if n_trials == 1:
        return 0.0

    em = 0.5772156649  # Euler-Mascheroni

    # Variance of SR estimator under H0 (Lo 2002 / Bailey & Lopez de Prado
    # eq (2) simplified for SR ~ 0).
    var_sr = max(
        (1.0 + (excess_kurtosis - 1.0) / 4.0) / max(n_obs_per_trial - 1, 1),
        1e-12,
    )

    # E[max] for n i.i.d. standard normals
    z = _norm_ppf(1.0 - 1.0 / n_trials)
    e_max_std = (1.0 - em) * z + em * _norm_ppf(1.0 - 1.0 / (n_trials * math.e))

    return e_max_std * math.sqrt(var_sr)


def deflated_sharpe(
    observed_sharpe: float,
    n_trials: int,
    returns: "Optional[Union[pd.Series, np.ndarray]]" = None,
    n_obs_per_trial: Optional[int] = None,
    confidence: float = 0.95,
) -> DeflatedSharpeResult:
    """Compute the Deflated Sharpe Ratio.

    Args:
        observed_sharpe: The Sharpe ratio observed in the backtest
            (annualized).
        n_trials: How many strategy variants were tried (selection
            overfit if you tried 100 and report the best).
        returns: Series of strategy returns; if provided, used to
            estimate skewness and excess kurtosis for higher accuracy.
        n_obs_per_trial: Length of the return series. Required if
            `returns` is not provided.
        confidence: Required confidence for `passes` (default 0.95).

    Returns:
        DeflatedSharpeResult with DSR, expected max SR, and pass/fail.
    """
    if n_trials < 1:
        raise ValueError(f"n_trials must be >= 1, got {n_trials}")

    if returns is not None:
        if isinstance(returns, pd.Series):
            n_obs_per_trial = n_obs_per_trial or len(returns)
        else:
            returns = np.asarray(returns, dtype=float)
            n_obs_per_trial = n_obs_per_trial or len(returns)
        skew, kurt = _higher_moments(returns)
    else:
        skew, kurt = 0.0, 0.0
        if n_obs_per_trial is None:
            raise ValueError(
                "Either `returns` or `n_obs_per_trial` must be provided"
            )

    sr = float(observed_sharpe)
    e_max = expected_max_sharpe(
        n_trials=n_trials,
        skewness=skew,
        excess_kurtosis=kurt,
        n_obs_per_trial=n_obs_per_trial,
    )

    var_sr = max(
        (1.0 + (kurt - 1.0) / 4.0) / max(n_obs_per_trial - 1, 1),
        1e-12,
    )

    if var_sr > 0 and math.isfinite(sr) and math.isfinite(e_max):
        z = (sr - e_max) / math.sqrt(var_sr)
        dsr = _norm_cdf(z)
    else:
        dsr = 0.0

    p_value = 1.0 - dsr
    passes = dsr >= confidence

    return DeflatedSharpeResult(
        observed_sharpe=sr,
        n_trials=n_trials,
        expected_max_sharpe=float(e_max),
        dsr=dsr,
        p_value=p_value,
        passes=passes,
    )
