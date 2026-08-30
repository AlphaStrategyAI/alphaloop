import json
import os
import subprocess
import venv
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from engine.execution import NotImplementedBroker, Order
from engine.export import build_strategy_pack, strategy_pack_eligibility
from engine.metrics import SimulationDiagnostics, SimulationReport, calculate_metrics
from engine.research.models import (
    AssetClass,
    Attempt,
    ChangeClass,
    Market,
    ResearchStatus,
    Reverification,
    ReviewReport,
    Round,
    Universe,
    Version,
    new_research,
)
from engine.strategy import (
    MarketPanel,
    MeanReversionStrategy,
    StrategySpec,
    run_daily_backtest,
)
from engine.verifiers import VerificationReport, VerifierResult

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def completed_research():
    base = new_research("r-export", NOW)
    gate = VerifierResult("scorecard.market", "scorecard-v1", True, {}, "fixture pass")
    simulation = accepted_report()
    attempt = Attempt(
        attempt_id="a-export",
        number=1,
        change_class=ChangeClass.MODEL,
        spec=reference_strategy().spec,
        simulation=simulation,
        verification=VerificationReport((gate, gate, gate, gate, gate)),
        review=ReviewReport(True, ()),
    )
    round_ = Round("r-export-v1-r1", 1, attempt, NOW)
    version = Version("r-export-v1", 1, base.brief, (round_,), NOW, "confirm_run")
    return replace(
        base,
        status=ResearchStatus.COMPLETED,
        versions=(version,),
        current_version_number=1,
        export_eligible=True,
        pending_confirm=None,
    )


def reference_strategy() -> MeanReversionStrategy:
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA", "BBB"))
    return MeanReversionStrategy(
        StrategySpec(
            id="mean-reversion-pack",
            thesis_locked="one-day reversal",
            universe=universe,
            frequency="1d",
            side="long_only",
            method_set=(),
            model_family="mean_reversion",
            lookback_days=2,
            entry_z=0.5,
        )
    )


def snapshot() -> MarketPanel:
    prices = pd.DataFrame(
        {"AAA": [10.0, 9.0, 10.0, 11.0], "BBB": [10.0, 11.0, 10.0, 9.0]},
        index=pd.date_range("2026-01-01", periods=4, tz=UTC),
    )
    benchmark = pd.Series(
        [100.0, 100.5, 100.0, 101.0],
        index=prices.index,
        name="SPX",
    )
    return MarketPanel(prices, NOW, benchmark)


def accepted_report() -> SimulationReport:
    strategy = reference_strategy()
    data = snapshot()
    strategy_returns = run_daily_backtest(strategy, data)
    assert data.benchmark_prices is not None
    benchmark_returns = data.benchmark_prices.pct_change(fill_method=None).fillna(0.0)
    return calculate_metrics(
        strategy_returns,
        benchmark_returns,
        "SPX",
        SimulationDiagnostics(
            sharpe_oos=0.7,
            sharpe_is=1.0,
            oos_segment_returns=(0.02, 0.01, -0.005),
            top_20_crowding_sharpe_impact=0.01,
            annual_turnover=1.0,
            covered_assets=2,
            missing_pct=0.0,
        ),
    )


def test_execution_port_is_explicitly_unavailable() -> None:
    broker = NotImplementedBroker()
    with pytest.raises(NotImplementedError, match="outside alphaloop v1"):
        broker.submit([Order("AAA", 1.0)])


def test_export_requires_completed_all_passed_no_pending_and_valid_reverify() -> None:
    research = completed_research()
    assert strategy_pack_eligibility(research).eligible
    assert not strategy_pack_eligibility(
        replace(research, status=ResearchStatus.RUNNING)
    ).eligible
    failed_gate = VerifierResult("overfit.walk", "walk-v1", False, {}, "failed rerun")
    failed_rerun = Reverification(
        round_id="r-export-v1-r1",
        method_id="overfit.walk",
        report=VerificationReport((failed_gate,)),
        passed=False,
        created_at=NOW,
    )
    assert not strategy_pack_eligibility(
        replace(research, reverifications=(failed_rerun,))
    ).eligible


def test_pack_runs_without_alphaloop_installed(tmp_path: Path) -> None:
    archive = build_strategy_pack(
        completed_research(),
        reference_strategy(),
        snapshot(),
        tmp_path / "strategy-pack.zip",
    )
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archive) as pack:
        pack.extractall(extracted)
        names = set(pack.namelist())
    assert {
        "manifest.json",
        "spec.json",
        "strategy.py",
        "execution.py",
        "run_backtest.py",
        "data/prices.csv",
        "data/benchmark.csv",
        "reports/metrics.json",
        "reports/verification.json",
        "reports/review.json",
        "materials/sources.json",
        "history/research.json",
        "schemas/strategy-pack.schema.json",
    } <= names

    environment = tmp_path / "clean-python"
    venv.EnvBuilder(with_pip=False).create(environment)
    isolated_python = (
        environment / "Scripts" / "python.exe"
        if os.name == "nt"
        else environment / "bin" / "python"
    )
    completed = subprocess.run(
        [isolated_python, "run_backtest.py"],
        cwd=extracted,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads((extracted / "results.json").read_text(encoding="utf-8"))
    assert result["strategy_id"] == "mean-reversion-pack"
    assert result["observations"] == 4
    accepted = completed_research().versions[-1].rounds[-1].accepted_attempt.simulation
    for field in (
        "r_total",
        "r_ann",
        "sharpe",
        "vol_ann",
        "max_drawdown",
        "r_bench_ann",
        "excess_ann",
        "tracking_error",
        "information_ratio",
    ):
        assert result[field] == pytest.approx(getattr(accepted, field), abs=1e-12)
    assert "alphaloop" not in (extracted / "run_backtest.py").read_text(encoding="utf-8")


def test_to_executable_uses_the_accepted_research_snapshot() -> None:
    strategy = reference_strategy()
    strategy.data_snapshot = snapshot()
    strategy.accepted_research = completed_research()
    archive = strategy.to_executable()
    assert archive.name == "strategy-pack.zip"
    assert archive.is_file()
