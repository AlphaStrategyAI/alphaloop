from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from engine.metrics import (
    SimulationDiagnostics,
    SimulationReport,
    benchmark_for,
    calculate_metrics,
)
from engine.research.gather import DataPort
from engine.strategy import AlphaStrategy, MarketPanel, run_daily_backtest


def simulate_daily(
    strategy: AlphaStrategy,
    data_port: DataPort,
    start: date,
    end: date,
    *,
    snapshot_path: Path | None = None,
) -> SimulationReport:
    benchmark = benchmark_for(strategy.universe)
    symbols = strategy.universe.symbols
    prices = data_port.load_daily(symbols, start, end)
    benchmark_prices = data_port.load_daily((benchmark.benchmark_id,), start, end)
    if snapshot_path is not None:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = prices.copy()
        snapshot["__benchmark__"] = benchmark_prices[benchmark.benchmark_id].reindex(
            snapshot.index
        )
        snapshot.to_csv(snapshot_path, index_label="date")
    panel = MarketPanel(
        prices,
        datetime.now(UTC),
        benchmark_prices[benchmark.benchmark_id],
    )
    strategy_returns = run_daily_backtest(strategy, panel)
    benchmark_returns = benchmark_prices[benchmark.benchmark_id].pct_change(fill_method=None).fillna(0.0)

    def sharpe(values: pd.Series) -> float:
        std = float(values.std(ddof=1))
        return 0.0 if std == 0.0 else float(values.mean() / std * (252**0.5))

    split_points = np.linspace(0, len(strategy_returns), 7, dtype=int)
    in_sample_sharpes = []
    out_sample_sharpes = []
    segment_returns = []
    for split in range(1, 6):
        train = strategy_returns.iloc[: split_points[split]]
        test = strategy_returns.iloc[split_points[split] : split_points[split + 1]]
        in_sample_sharpes.append(sharpe(train))
        out_sample_sharpes.append(sharpe(test))
        segment_returns.append(float((1.0 + test).prod() - 1.0))  # type: ignore[operator, arg-type]
    raw_signals = strategy.generate_signals(panel).shift(1).fillna(0.0)
    gross = raw_signals.abs().sum(axis=1).replace(0.0, 1.0)
    weights = raw_signals.div(gross, axis=0)
    concentration = weights.abs().max(axis=1)
    crowded = strategy_returns[concentration >= concentration.quantile(0.8)]
    diagnostics = SimulationDiagnostics(
        sharpe_oos=float(np.mean(out_sample_sharpes)),
        sharpe_is=float(np.mean(in_sample_sharpes)),
        oos_segment_returns=tuple(segment_returns),
        top_20_crowding_sharpe_impact=sharpe(crowded),
        annual_turnover=float(weights.diff().abs().sum().sum() / len(prices) * 252),
        covered_assets=int(prices.notna().any(axis=0).sum()),
        missing_pct=float(prices.isna().to_numpy().mean() * 100),
    )
    return calculate_metrics(
        strategy_returns,
        benchmark_returns,
        benchmark.benchmark_id,
        diagnostics,
    )
