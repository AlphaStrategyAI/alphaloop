from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from engine.metrics import (
    SimulationDiagnostics,
    benchmark_for,
    calculate_metrics,
)
from engine.research.models import AssetClass, Market, Universe
from engine.research.simulate import simulate_daily
from engine.strategy import MarketPanel, MeanReversionStrategy, StrategySpec


@pytest.mark.parametrize(
    ("universe", "expected"),
    (
        (Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("A",)), "SPX"),
        (Universe(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY, ("A",)), "000300.SH"),
        (Universe(Market.US, AssetClass.BOND, AssetClass.BOND, ("B",)), "AGG"),
        (Universe(Market.CN, AssetClass.BOND, AssetClass.BOND, ("B",)), "CBA00101.CS"),
        (Universe(Market.US, AssetClass.FUND, AssetClass.EQUITY, ("F",)), "SPX"),
        (Universe(Market.CN, AssetClass.FUND, AssetClass.BOND, ("F",)), "CBA00101.CS"),
    ),
)
def test_benchmark_is_selected_by_market_and_underlying_asset(
    universe: Universe,
    expected: str,
) -> None:
    assert benchmark_for(universe).benchmark_id == expected


def test_required_metrics_are_compounded_and_finite() -> None:
    index = pd.date_range("2026-01-01", periods=4, tz=UTC)
    strategy = pd.Series([0.10, -0.05, 0.02, 0.01], index=index)
    benchmark = pd.Series([0.04, -0.01, 0.01, 0.00], index=index)
    diagnostics = SimulationDiagnostics(
        sharpe_oos=0.8,
        sharpe_is=1.0,
        oos_segment_returns=(0.02, 0.03, 0.01),
        top_20_crowding_sharpe_impact=0.05,
        annual_turnover=1.0,
        covered_assets=2,
        missing_pct=0.0,
    )

    report = calculate_metrics(strategy, benchmark, "SPX", diagnostics)

    assert report.r_total == pytest.approx((1.10 * 0.95 * 1.02 * 1.01) - 1)
    assert report.benchmark_id == "SPX"
    assert report.r_ann > report.r_bench_ann
    assert report.excess_ann == pytest.approx(report.r_ann - report.r_bench_ann)
    assert report.vol_ann > 0
    assert report.max_drawdown == pytest.approx(-0.05)
    assert report.tracking_error > 0
    assert report.information_ratio == pytest.approx(
        report.excess_ann / report.tracking_error
    )


class FakeData:
    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        index = pd.date_range(start, periods=40, tz=UTC)
        return pd.DataFrame(
            {symbol: [100.0 + day + offset for day in range(40)] for offset, symbol in enumerate(symbols)},
            index=index,
        )


def test_daily_simulation_fetches_strategy_and_benchmark() -> None:
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA", "BBB"))
    strategy = MeanReversionStrategy(
        StrategySpec(
            id="s-1",
            thesis_locked="reversal",
            universe=universe,
            frequency="1d",
            side="long_only",
            method_set=(),
            model_family="mean_reversion",
            lookback_days=2,
            entry_z=0.5,
        )
    )
    report = simulate_daily(strategy, FakeData(), date(2025, 1, 1), date(2026, 1, 1))
    assert report.benchmark_id == "SPX"
    assert report.observations == 40
