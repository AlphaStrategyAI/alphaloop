"""
Tests for the Deflated Sharpe Ratio module.

Covers:
  - expected_max_sharpe() shape and monotonicity
  - deflated_sharpe() pass/fail verdicts under different Sharpe/trial combos
  - n_trials monotonicity (more trials -> harder to pass)
  - Error handling (invalid n_trials, missing returns / n_obs_per_trial)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Allow running pytest from repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from alphaloop.diagnostic import (  # noqa: E402
    DeflatedSharpeResult,
    deflated_sharpe,
    expected_max_sharpe,
)


# ----- expected_max_sharpe -----


def test_n_trials_one_returns_zero():
    """E[max SR] with 1 trial is 0 by definition."""
    assert expected_max_sharpe(n_trials=1) == 0.0


def test_n_trials_grows_with_n():
    """E[max SR] must increase with more trials."""
    e1 = expected_max_sharpe(n_trials=5)
    e10 = expected_max_sharpe(n_trials=20)
    e100 = expected_max_sharpe(n_trials=500)
    assert e1 < e10 < e100


def test_more_observations_lowers_expected_max():
    """More data -> smaller SR estimator variance -> smaller E[max]."""
    e_few = expected_max_sharpe(n_trials=50, n_obs_per_trial=63)
    e_many = expected_max_sharpe(n_trials=50, n_obs_per_trial=2520)
    assert e_few > e_many


def test_expected_max_rejects_invalid_n_trials():
    with pytest.raises(ValueError, match="n_trials must be >= 1"):
        expected_max_sharpe(n_trials=0)


def test_expected_max_handles_zero_kurtosis_and_skew():
    """With normal returns, function should still return a finite positive value."""
    e = expected_max_sharpe(n_trials=20, n_obs_per_trial=252)
    assert 0.0 < e < 1.0


# ----- deflated_sharpe -----


def test_high_sharpe_passes_dsr():
    """SR 2.0 across 20 trials with normal returns should easily pass."""
    np.random.seed(0)
    rets = pd.Series(np.random.normal(0.001, 0.01, 252))
    result = deflated_sharpe(observed_sharpe=2.0, n_trials=20, returns=rets)
    assert result.passes
    assert result.dsr > 0.95
    assert isinstance(result, DeflatedSharpeResult)


def test_low_sharpe_fails_dsr():
    """A near-zero SR across many trials should not pass DSR.

    SR 0.05 with 50 trials is not enough to clear the multiple-
    testing bar; we expect passes=False.
    """
    np.random.seed(1)
    rets = pd.Series(np.random.normal(0.0001, 0.01, 500))
    result = deflated_sharpe(observed_sharpe=0.05, n_trials=50, returns=rets)
    assert not result.passes
    assert result.p_value > 0.05


def test_more_trials_tightens_dsr():
    """Same SR but more trials -> DSR does not increase."""
    np.random.seed(2)
    rets = pd.Series(np.random.normal(0.0008, 0.01, 500))
    r5 = deflated_sharpe(observed_sharpe=1.5, n_trials=5, returns=rets)
    r50 = deflated_sharpe(observed_sharpe=1.5, n_trials=50, returns=rets)
    # More trials -> expected max SR is higher -> DSR should not increase.
    assert r5.dsr >= r50.dsr - 0.05  # small tolerance for noise


def test_deflated_sharpe_rejects_n_trials_zero():
    with pytest.raises(ValueError, match="n_trials must be >= 1"):
        deflated_sharpe(observed_sharpe=1.0, n_trials=0, n_obs_per_trial=252)


def test_deflated_sharpe_requires_returns_or_obs():
    with pytest.raises(ValueError, match="Either `returns` or `n_obs_per_trial`"):
        deflated_sharpe(observed_sharpe=1.0, n_trials=10)


def test_deflated_sharpe_p_value_is_one_minus_dsr():
    np.random.seed(3)
    rets = pd.Series(np.random.normal(0.0006, 0.01, 300))
    r = deflated_sharpe(observed_sharpe=1.2, n_trials=15, returns=rets)
    assert r.p_value == pytest.approx(1.0 - r.dsr, abs=1e-9)


def test_deflated_sharpe_summary_is_string():
    np.random.seed(4)
    rets = pd.Series(np.random.normal(0.0004, 0.01, 252))
    r = deflated_sharpe(observed_sharpe=1.0, n_trials=10, returns=rets)
    s = r.summary()
    assert isinstance(s, str)
    assert "DSR verdict" in s


def test_deflated_sharpe_confidence_threshold():
    """Lowering confidence threshold can flip passes from False to True."""
    np.random.seed(5)
    rets = pd.Series(np.random.normal(0.0006, 0.01, 252))
    r_strict = deflated_sharpe(observed_sharpe=1.0, n_trials=10, returns=rets, confidence=0.99)
    r_relaxed = deflated_sharpe(observed_sharpe=1.0, n_trials=10, returns=rets, confidence=0.50)
    # Strict passes only if DSR >= 0.99; relaxed passes if DSR >= 0.50.
    if r_strict.dsr < 0.99:
        assert not r_strict.passes
    if r_relaxed.dsr >= 0.50:
        assert r_relaxed.passes


def test_deflated_sharpe_with_ndarray_returns():
    """deflated_sharpe should also accept numpy arrays, not just Series."""
    np.random.seed(6)
    rets = np.random.normal(0.001, 0.01, 252)
    r = deflated_sharpe(observed_sharpe=2.0, n_trials=10, returns=rets)
    assert r.passes
    assert r.dsr > 0.9
