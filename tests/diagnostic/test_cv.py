"""
Tests for walk_forward_cv().
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from alphaloop.diagnostic import (  # noqa: E402
    WalkForwardFold,
    WalkForwardResult,
    walk_forward_cv,
)
from alphaloop.diagnostic.cv import chronological_half_sharpes, majority_fold_ok  # noqa: E402


def _make_prices(n: int = 1000, seed: int = 0, drift: float = 0.0003) -> pd.Series:
    """Random walk with a positive drift."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, 0.01, n)
    prices = 100.0 * np.exp(np.cumsum(rets))
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series(prices, index=idx)


def _buy_and_hold(prices: pd.Series) -> pd.Series:
    return pd.Series(1.0, index=prices.index)


def test_walk_forward_returns_result_dataclass():
    prices = _make_prices(500)
    result = walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=50, step_size=50)
    assert isinstance(result, WalkForwardResult)
    assert result.n_folds >= 1


def test_walk_forward_folds_have_correct_types():
    prices = _make_prices(500)
    result = walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=50)
    for f in result.folds:
        assert isinstance(f, WalkForwardFold)
        assert isinstance(f.oos_sharpe, float)


def test_walk_forward_default_step_equals_test_size():
    """step_size=None defaults to test_size (non-overlapping test windows)."""
    prices = _make_prices(1000)
    result = walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=63, step_size=None)
    # The number of folds with non-overlapping windows is roughly
    # (n - train_size) / test_size.
    expected = (1000 - 200) // 63
    assert result.n_folds == expected


def test_walk_forward_buy_and_hold_is_profitable():
    """With positive drift, buy-and-hold should have positive OOS Sharpe on average."""
    prices = _make_prices(1000, drift=0.001)
    result = walk_forward_cv(prices, _buy_and_hold, train_size=252, test_size=63)
    assert result.oos_sharpe_mean > 0
    assert result.passes


def test_walk_forward_rejects_short_series():
    prices = _make_prices(100)
    with pytest.raises(ValueError, match="Need at least"):
        walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=50)


def test_walk_forward_rejects_non_series():
    with pytest.raises(TypeError, match="must be a pandas Series"):
        walk_forward_cv([1, 2, 3], _buy_and_hold, train_size=2, test_size=1)


def test_walk_forward_empty_result_on_impossible_params():
    """train_size+test_size > n but somehow pass — should produce 0 folds."""
    prices = _make_prices(10)
    with pytest.raises(ValueError):
        walk_forward_cv(prices, _buy_and_hold, train_size=20, test_size=5)


def test_walk_forward_step_smaller_than_test_creates_overlap():
    """step_size < test_size -> overlapping test windows, more folds."""
    prices = _make_prices(1000)
    r_disjoint = walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=63, step_size=63)
    r_overlap = walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=63, step_size=21)
    assert r_overlap.n_folds >= r_disjoint.n_folds


def test_walk_forward_negative_drift_fails():
    """With negative drift, buy-and-hold OOS Sharpe should be negative."""
    prices = _make_prices(1000, drift=-0.001)
    result = walk_forward_cv(prices, _buy_and_hold, train_size=252, test_size=63)
    assert result.oos_sharpe_mean < 0
    assert not result.passes


def test_walk_forward_summary_is_string():
    prices = _make_prices(500)
    result = walk_forward_cv(prices, _buy_and_hold, train_size=200, test_size=63)
    s = result.summary()
    assert isinstance(s, str)
    assert "Walk-Forward CV verdict" in s


def test_walk_forward_exposes_concatenated_oos_returns():
    prices = _make_prices(400)
    result = walk_forward_cv(
        prices, _buy_and_hold, train_size=200, test_size=50, embargo_size=0, step_size=50
    )
    assert result.n_folds >= 1
    assert len(result.oos_returns) == result.n_folds * 50
    assert list(result.oos_returns.index[:50]) == list(prices.index[200:250])


def test_walk_forward_strategy_fn_sees_history_through_test():
    prices = _make_prices(400)
    seen: list[int] = []

    def spy(series: pd.Series) -> pd.Series:
        seen.append(len(series))
        return pd.Series(1.0, index=series.index)

    walk_forward_cv(
        prices, spy, train_size=200, test_size=50, embargo_size=5, step_size=50
    )
    assert seen
    assert all(length >= 200 + 5 + 50 for length in seen)


def test_walk_forward_embargo_gaps_train_and_test():
    prices = _make_prices(400)
    result = walk_forward_cv(
        prices, _buy_and_hold, train_size=200, test_size=50, embargo_size=5, step_size=55
    )
    assert result.n_folds >= 1
    for fold in result.folds:
        train_end_i = prices.index.get_loc(fold.train_end)
        test_start_i = prices.index.get_loc(fold.test_start)
        assert int(test_start_i) - int(train_end_i) - 1 == 5


def test_chronological_half_sharpes_both_positive():
    rng = np.random.default_rng(0)
    rets = pd.Series(
        np.concatenate(
            [rng.normal(0.01, 0.002, 20), rng.normal(0.01, 0.002, 20)]
        )
    )
    first, second, evaluated = chronological_half_sharpes(rets)
    assert evaluated is True
    assert first > 0
    assert second > 0


def test_chronological_half_sharpes_second_half_negative():
    rng = np.random.default_rng(0)
    rets = pd.Series(
        np.concatenate(
            [rng.normal(0.01, 0.002, 20), rng.normal(-0.01, 0.002, 20)]
        )
    )
    first, second, evaluated = chronological_half_sharpes(rets)
    assert evaluated is True
    assert first > 0
    assert second < 0


def test_chronological_half_sharpes_short_not_evaluated():
    first, second, evaluated = chronological_half_sharpes(pd.Series([0.01] * 20))
    assert evaluated is False
    assert first == 0.0
    assert second == 0.0


def test_walk_forward_fails_when_second_oos_half_is_negative():
    n = 400
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    rng = np.random.default_rng(1)
    rets = np.concatenate(
        [rng.normal(0.004, 0.002, 300), rng.normal(-0.002, 0.002, 100)]
    )
    prices = pd.Series(100.0 * np.exp(np.cumsum(rets)), index=idx)
    result = walk_forward_cv(
        prices, _buy_and_hold, train_size=200, test_size=50, step_size=50
    )
    assert len(result.oos_returns) >= 30
    assert result.oos_sharpe_mean > 0
    assert result.first_half_sharpe > 0
    assert result.second_half_sharpe < 0
    assert result.regime_stable is False
    assert result.passes is False


def test_walk_forward_does_not_fail_regime_when_oos_short():
    prices = _make_prices(50, drift=0.001)
    result = walk_forward_cv(
        prices, _buy_and_hold, train_size=20, test_size=8, step_size=8
    )
    assert len(result.oos_returns) < 30
    assert result.regime_stable is True


def test_walk_forward_fails_when_median_fold_sharpe_is_negative():
    n = 350
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    rng = np.random.default_rng(2)
    rets = np.concatenate(
        [
            rng.normal(0.0003, 0.01, 200),
            rng.normal(-0.0015, 0.002, 50),
            rng.normal(0.008, 0.002, 50),
            rng.normal(-0.0015, 0.002, 50),
        ]
    )
    prices = pd.Series(100.0 * np.exp(np.cumsum(rets)), index=idx)
    result = walk_forward_cv(
        prices, _buy_and_hold, train_size=200, test_size=50, step_size=50
    )
    assert result.n_folds == 3
    assert result.oos_sharpe_mean > 0
    assert result.regime_stable is True
    assert result.oos_sharpe_median < 0
    assert result.passes is False


def test_majority_fold_ok_even_split_is_not_majority():
    n_positive, ok = majority_fold_ok([-1.0, -0.5, 0.6, 2.0], 0.0)
    assert n_positive == 2
    assert ok is False


def test_majority_fold_ok_skipped_when_fewer_than_three_folds():
    n_positive, ok = majority_fold_ok([-1.0, 2.0], 0.0)
    assert n_positive == 1
    assert ok is True


def test_majority_fold_ok_three_folds_need_two_positive():
    n_positive, ok = majority_fold_ok([-0.1, 0.2, 0.3], 0.0)
    assert n_positive == 2
    assert ok is True


def test_majority_fold_ok_nonfinite_does_not_count():
    n_positive, ok = majority_fold_ok([float("nan"), 0.2, 0.3], 0.0)
    assert n_positive == 2
    assert ok is True


def test_walk_forward_fails_when_only_half_of_even_folds_are_positive():
    n = 400
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    rng = np.random.default_rng(4)
    rets = np.concatenate(
        [
            rng.normal(0.0002, 0.002, 200),
            rng.normal(0.008, 0.002, 50),
            rng.normal(-0.002, 0.002, 50),
            rng.normal(0.004, 0.002, 50),
            rng.normal(-0.002, 0.002, 50),
        ]
    )
    prices = pd.Series(100.0 * np.exp(np.cumsum(rets)), index=idx)
    result = walk_forward_cv(
        prices, _buy_and_hold, train_size=200, test_size=50, step_size=50
    )
    assert result.n_folds == 4
    assert result.oos_sharpe_mean > 0
    assert result.oos_sharpe_median > 0
    assert result.regime_stable is True
    assert result.n_positive_folds == 2
    assert result.majority_stable is False
    assert result.passes is False


def test_cpcv_not_evaluated_when_series_is_short():
    from math import comb

    from alphaloop.diagnostic.cv import combinatorial_purged_cv

    prices = _make_prices(80, drift=0.001)
    result = combinatorial_purged_cv(prices, _buy_and_hold)
    assert result.evaluated is False
    assert result.n_paths == 0
    assert comb(6, 2) == 15


def test_cpcv_positive_drift_buy_and_hold_passes():
    from math import comb

    from alphaloop.diagnostic.cv import combinatorial_purged_cv

    prices = _make_prices(180, drift=0.003)
    result = combinatorial_purged_cv(prices, _buy_and_hold, embargo_size=1)
    assert result.evaluated is True
    assert result.n_groups == 6
    assert result.n_test_groups == 2
    assert result.n_paths == comb(6, 2)
    assert result.oos_sharpe_mean > 0
    assert result.oos_sharpe_median > 0
    assert result.majority_stable is True
    assert result.passes is True


def test_cpcv_negative_drift_fails():
    from alphaloop.diagnostic.cv import combinatorial_purged_cv

    prices = _make_prices(180, drift=-0.003)
    result = combinatorial_purged_cv(prices, _buy_and_hold, embargo_size=1)
    assert result.evaluated is True
    assert result.oos_sharpe_mean < 0
    assert result.passes is False


def test_select_cpcv_shape_prefers_textbook_when_long_enough():
    from alphaloop.diagnostic.cv import select_cpcv_shape

    assert select_cpcv_shape(80) is None
    assert select_cpcv_shape(180) == (6, 2)
    assert select_cpcv_shape(319) == (6, 2)
    assert select_cpcv_shape(320) == (16, 8)


def test_cpcv_textbook_partition_when_sample_is_long():
    from math import comb

    from alphaloop.diagnostic.cv import combinatorial_purged_cv

    prices = _make_prices(320, drift=0.003)
    result = combinatorial_purged_cv(prices, _buy_and_hold, embargo_size=1)
    assert result.evaluated is True
    assert result.n_groups == 16
    assert result.n_test_groups == 8
    assert result.n_paths == comb(16, 8)
    assert result.n_positive_paths * 2 > result.n_paths
    assert result.majority_stable is True
    assert result.oos_sharpe_mean > 0
    assert result.oos_sharpe_median > 0
    assert result.passes is True


def test_cpcv_explicit_groups_override_auto_shape():
    from math import comb

    from alphaloop.diagnostic.cv import combinatorial_purged_cv

    prices = _make_prices(320, drift=0.003)
    result = combinatorial_purged_cv(
        prices,
        _buy_and_hold,
        n_groups=6,
        n_test_groups=2,
        embargo_size=1,
    )
    assert result.n_groups == 6
    assert result.n_paths == comb(6, 2)
    assert result.passes is True
