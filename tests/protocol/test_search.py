from alphaloop.protocol.search import method_parameter_grid
from alphaloop.protocol.stop import RevisionKind, classify_revision
from alphaloop.contracts.research_spec import Hypothesis


def _hypothesis() -> Hypothesis:
    return Hypothesis(
        statement="s",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
    )


def test_grid_starts_with_defaults():
    grid = method_parameter_grid("momentum_12_1")
    assert grid[0] == {}
    assert {"lookback": 126, "skip": 21} in grid
    assert {"lookback": 189, "skip": 21} in grid
    assert len(grid) == 3


def test_grid_entries_are_method_revisions():
    frozen = _hypothesis()
    for params in method_parameter_grid("momentum_12_1"):
        kind = classify_revision(frozen, ("dsr",), params)
        assert kind is RevisionKind.METHOD


def test_unknown_kind_has_only_defaults():
    assert method_parameter_grid("NotAClass") == ({},)


def test_rsi_grid_is_wilder_variants():
    grid = method_parameter_grid("rsi")
    assert grid[0] == {}
    assert {"window": 9} in grid
    assert {"window": 21} in grid
    assert len(grid) == 3
    frozen = _hypothesis()
    for params in grid:
        assert classify_revision(frozen, ("dsr",), params) is RevisionKind.METHOD


def test_roc_grid_is_formation_windows():
    grid = method_parameter_grid("roc")
    assert grid[0] == {}
    assert {"window": 63} in grid
    assert {"window": 126} in grid
    assert len(grid) == 3


def test_macd_grid_is_appel_variants():
    grid = method_parameter_grid("macd")
    assert grid[0] == {}
    assert {"fast": 8, "slow": 17, "signal_period": 9} in grid
    assert {"fast": 12, "slow": 25, "signal_period": 9} in grid
    assert len(grid) == 3
    frozen = _hypothesis()
    for params in grid:
        assert classify_revision(frozen, ("dsr",), params) is RevisionKind.METHOD
