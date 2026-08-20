"""Tests for nested_holdout_bounds()."""
from __future__ import annotations

from alphaloop.diagnostic.holdout import nested_holdout_bounds


def test_nested_holdout_bounds_none_when_short():
    assert nested_holdout_bounds(80, 252) is None
    assert nested_holdout_bounds(186, 252) is None


def test_nested_holdout_bounds_on_us_equity_daily():
    bounds = nested_holdout_bounds(260, 252)
    assert bounds is not None
    inner_end, holdout_start, holdout_end = bounds
    assert holdout_end == 260
    assert holdout_start == 260 - 63
    assert inner_end == holdout_start - 4
    assert inner_end >= 120
