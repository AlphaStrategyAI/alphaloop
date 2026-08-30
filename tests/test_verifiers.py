from dataclasses import replace

import pytest

from engine.metrics import SimulationReport
from engine.research.models import AssetClass, Market, Universe
from engine.strategy import StrategySpec
from engine.verifiers import VERIFIER_REVISIONS, run_verifiers


def spec(market: Market = Market.US) -> StrategySpec:
    universe = Universe(market, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA",))
    return StrategySpec(
        id="s-verify",
        thesis_locked="reversal",
        universe=universe,
        frequency="1d",
        side="long_only",
        method_set=(),
        model_family="mean_reversion",
        lookback_days=20,
        entry_z=1.0,
        max_drawdown_floor=-0.25,
    )


def passing_report() -> SimulationReport:
    return SimulationReport(
        r_total=0.20,
        r_ann=0.12,
        sharpe=0.9,
        vol_ann=0.13,
        max_drawdown=-0.20,
        benchmark_id="SPX",
        r_bench_ann=0.08,
        excess_ann=0.04,
        tracking_error=0.06,
        information_ratio=2 / 3,
        sharpe_oos=0.7,
        sharpe_is=1.0,
        oos_segment_returns=(0.02, 0.01, -0.005),
        top_20_crowding_sharpe_impact=0.01,
        annual_turnover=1.0,
        observations=756,
        covered_assets=1,
        missing_pct=0.0,
    )


def test_primary_scorecard_and_all_four_verifiers_pass() -> None:
    result = run_verifiers(passing_report(), spec())
    assert [gate.verifier_id for gate in result.results] == [
        "scorecard.market",
        "overfit.walk",
        "stability.oos",
        "crowding.load",
        "cost.turnover",
    ]
    assert result.passed


@pytest.mark.parametrize(
    ("field", "value", "failed"),
    (
        ("sharpe_oos", 0.0, "scorecard.market"),
        ("excess_ann", 0.0, "scorecard.market"),
        ("max_drawdown", -0.26, "scorecard.market"),
        ("sharpe_oos", 0.5, "overfit.walk"),
        ("oos_segment_returns", (0.01, -0.01, 0.0), "stability.oos"),
        ("top_20_crowding_sharpe_impact", -0.01, "crowding.load"),
        ("annual_turnover", 50.0, "cost.turnover"),
    ),
)
def test_each_locked_gate_can_fail(field: str, value: object, failed: str) -> None:
    result = run_verifiers(replace(passing_report(), **{field: value}), spec())
    assert failed in {gate.verifier_id for gate in result.results if not gate.passed}
    assert not result.passed


def test_costs_are_10bp_us_and_20bp_cn() -> None:
    assert VERIFIER_REVISIONS["overfit.walk"]["n_splits"] == 5
    assert VERIFIER_REVISIONS["cost.turnover"]["us_cost_bp"] == 10
    assert VERIFIER_REVISIONS["cost.turnover"]["cn_cost_bp"] == 20
    us = run_verifiers(passing_report(), spec(Market.US))
    cn = run_verifiers(passing_report(), spec(Market.CN))
    us_cost = next(item for item in us.results if item.verifier_id == "cost.turnover")
    cn_cost = next(item for item in cn.results if item.verifier_id == "cost.turnover")
    assert us_cost.values["cost_drag"] == pytest.approx(0.001)
    assert cn_cost.values["cost_drag"] == pytest.approx(0.002)
