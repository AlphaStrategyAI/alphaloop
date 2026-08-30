from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

from engine.research.models import AssetClass, Market, Universe

TRADING_DAYS = 252


@dataclass(frozen=True, slots=True)
class BenchmarkSpec:
    benchmark_id: str
    name: str
    return_kind: str


BENCHMARKS = {
    (Market.US, AssetClass.EQUITY): BenchmarkSpec("SPX", "S&P 500", "price_index"),
    (Market.CN, AssetClass.EQUITY): BenchmarkSpec("000300.SH", "CSI 300", "price_index"),
    (Market.US, AssetClass.BOND): BenchmarkSpec("AGG", "Bloomberg US Agg ETF proxy", "total_return_proxy"),
    (Market.CN, AssetClass.BOND): BenchmarkSpec(
        "CBA00101.CS",
        "ChinaBond New Composite Wealth Index",
        "wealth_index",
    ),
}


@dataclass(frozen=True, slots=True)
class SimulationDiagnostics:
    sharpe_oos: float
    sharpe_is: float
    oos_segment_returns: tuple[float, ...]
    top_20_crowding_sharpe_impact: float
    annual_turnover: float
    covered_assets: int
    missing_pct: float


@dataclass(frozen=True, slots=True)
class SimulationReport:
    r_total: float
    r_ann: float
    sharpe: float
    vol_ann: float
    max_drawdown: float
    benchmark_id: str
    r_bench_ann: float
    excess_ann: float
    tracking_error: float
    information_ratio: float
    sharpe_oos: float
    sharpe_is: float
    oos_segment_returns: tuple[float, ...]
    top_20_crowding_sharpe_impact: float
    annual_turnover: float
    observations: int
    covered_assets: int
    missing_pct: float


def benchmark_for(universe: Universe) -> BenchmarkSpec:
    return BENCHMARKS[(universe.market, universe.underlying_asset_class)]


def _annualized_return(returns: pd.Series) -> float:
    total = float((1.0 + returns).prod() - 1.0)  # type: ignore[operator, arg-type]
    return float((1.0 + total) ** (TRADING_DAYS / len(returns)) - 1.0)


def _ratio(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0.0 else numerator / denominator


def calculate_metrics(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    benchmark_id: str,
    diagnostics: SimulationDiagnostics,
) -> SimulationReport:
    aligned = pd.concat(
        [strategy_returns.rename("strategy"), benchmark_returns.rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna()
    if aligned.empty or not np.isfinite(aligned.to_numpy()).all():
        raise ValueError("strategy and benchmark need finite overlapping daily returns")
    strategy = aligned["strategy"]
    benchmark = aligned["benchmark"]
    r_total = float((1.0 + strategy).prod() - 1.0)  # type: ignore[operator, arg-type]
    r_ann = _annualized_return(strategy)
    r_bench_ann = _annualized_return(benchmark)
    vol_ann = float(strategy.std(ddof=1) * sqrt(TRADING_DAYS))
    sharpe = _ratio(float(strategy.mean() * TRADING_DAYS), vol_ann)
    wealth = (1.0 + strategy).cumprod()
    max_drawdown = float((wealth / wealth.cummax() - 1.0).min())
    tracking_error = float((strategy - benchmark).std(ddof=1) * sqrt(TRADING_DAYS))
    excess_ann = r_ann - r_bench_ann
    return SimulationReport(
        r_total=r_total,
        r_ann=r_ann,
        sharpe=sharpe,
        vol_ann=vol_ann,
        max_drawdown=max_drawdown,
        benchmark_id=benchmark_id,
        r_bench_ann=r_bench_ann,
        excess_ann=excess_ann,
        tracking_error=tracking_error,
        information_ratio=_ratio(excess_ann, tracking_error),
        sharpe_oos=diagnostics.sharpe_oos,
        sharpe_is=diagnostics.sharpe_is,
        oos_segment_returns=diagnostics.oos_segment_returns,
        top_20_crowding_sharpe_impact=diagnostics.top_20_crowding_sharpe_impact,
        annual_turnover=diagnostics.annual_turnover,
        observations=len(aligned),
        covered_assets=diagnostics.covered_assets,
        missing_pct=diagnostics.missing_pct,
    )
