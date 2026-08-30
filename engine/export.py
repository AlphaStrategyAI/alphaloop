from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from engine.research.models import Research, ResearchStatus
from engine.strategy import AlphaStrategy, MarketPanel, MeanReversionStrategy
from engine.verifiers import VERIFIER_REVISIONS


@dataclass(frozen=True, slots=True)
class ExportEligibility:
    eligible: bool
    failed_checks: tuple[str, ...]


def strategy_pack_eligibility(research: Research) -> ExportEligibility:
    current_attempt = (
        research.versions[-1].rounds[-1].accepted_attempt
        if research.versions and research.versions[-1].rounds
        else None
    )
    checks = {
        "completed": research.status is ResearchStatus.COMPLETED,
        "all_current_methods_passed": (
            current_attempt is not None and current_attempt.verification.passed
        ),
        "no_pending_confirm": research.pending_confirm is None,
        "all_reverifies_passed": all(
            reverification.passed
            for reverification in research.reverifications
            if current_attempt is not None
            and reverification.round_id
            == research.versions[-1].rounds[-1].round_id
        ),
    }
    return ExportEligibility(
        eligible=all(checks.values()),
        failed_checks=tuple(name for name, passed in checks.items() if not passed),
    )


def _json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=str),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


STRATEGY_MODULE = '''import csv
import json
import math
import statistics
from pathlib import Path

TRADING_DAYS = 252


def _returns(values):
    """Calculate percentage returns with None for the first value (no prior)."""
    return [None] + [
        values[index] / values[index - 1] - 1.0
        for index in range(1, len(values))
    ]


def _annualized(values):
    total = math.prod(1.0 + value for value in values) - 1.0
    return (1.0 + total) ** (TRADING_DAYS / len(values)) - 1.0


def _metrics(strategy, benchmark):
    total = math.prod(1.0 + value for value in strategy) - 1.0
    r_ann = _annualized(strategy)
    r_bench_ann = _annualized(benchmark)
    vol = statistics.stdev(strategy) * math.sqrt(TRADING_DAYS)
    wealth = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in strategy:
        wealth *= 1.0 + value
        peak = max(peak, wealth)
        max_drawdown = min(max_drawdown, wealth / peak - 1.0)
    active = [left - right for left, right in zip(strategy, benchmark)]
    tracking_error = statistics.stdev(active) * math.sqrt(TRADING_DAYS)
    excess = r_ann - r_bench_ann
    return {
        "r_total": total,
        "r_ann": r_ann,
        "sharpe": 0.0 if vol == 0.0 else statistics.mean(strategy) * TRADING_DAYS / vol,
        "vol_ann": vol,
        "max_drawdown": max_drawdown,
        "r_bench_ann": r_bench_ann,
        "excess_ann": excess,
        "tracking_error": tracking_error,
        "information_ratio": 0.0 if tracking_error == 0.0 else excess / tracking_error,
    }


def backtest(root: Path) -> dict:
    spec = json.loads((root / "spec.json").read_text(encoding="utf-8"))
    with (root / "data" / "prices.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with (root / "data" / "benchmark.csv").open(newline="", encoding="utf-8") as handle:
        benchmark_rows = list(csv.DictReader(handle))
    symbols = spec["universe"]["symbols"]
    lookback = int(spec["lookback_days"])
    entry_z = float(spec["entry_z"])
    values = {symbol: [float(row[symbol]) for row in rows] for symbol in symbols}
    asset_returns = {symbol: _returns(series) for symbol, series in values.items()}
    signals = []
    for index in range(len(rows)):
        scores = {}
        for symbol in symbols:
            window = [
                r for r in asset_returns[symbol][max(0, index - lookback + 1) : index + 1]
                if r is not None
            ]
            scores[symbol] = -statistics.mean(window) if len(window) == lookback else 0.0
        all_zero = all(s == 0.0 for s in scores.values())
        if all_zero:
            signals.append({symbol: 0.0 for symbol in symbols})
            continue
        dispersion = statistics.stdev(scores.values()) if len(scores) > 1 else 0.0
        center = statistics.mean(scores.values())
        row = {}
        for symbol, score in scores.items():
            zscore = 0.0 if dispersion == 0.0 else (score - center) / dispersion
            row[symbol] = (
                1.0
                if zscore >= entry_z
                else -1.0
                if spec["side"] == "long_short" and zscore <= -entry_z
                else 0.0
            )
        signals.append(row)
    strategy_returns = []
    for index in range(len(rows)):
        prior = signals[index - 1] if index > 0 else {symbol: 0.0 for symbol in symbols}
        gross = sum(abs(value) for value in prior.values()) or 1.0
        ret = asset_returns[symbols[0]][index]
        if ret is None:
            ret = 0.0
        strategy_returns.append(
            sum(
                prior[symbol] / gross * (asset_returns[symbol][index] or 0.0)
                for symbol in symbols
            )
        )
    benchmark_returns = [
        0.0 if r is None else r
        for r in _returns([float(row["benchmark"]) for row in benchmark_rows])
    ]
    return {
        "strategy_id": spec["id"],
        "benchmark_id": spec["benchmark_id"],
        "observations": len(rows),
        **_metrics(strategy_returns, benchmark_returns),
    }
'''

RUNNER = '''import json
from pathlib import Path
from strategy import backtest

root = Path(__file__).resolve().parent
result = backtest(root)
(root / "results.json").write_text(
    json.dumps(result, sort_keys=True, indent=2),
    encoding="utf-8",
)
print(json.dumps(result, sort_keys=True))
'''

EXECUTION_STUB = '''from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class Order:
    asset: str
    target_weight: float

class ExecutionPort(Protocol):
    def submit(self, orders: list[Order]) -> None:
        raise NotImplementedError

class Broker(ExecutionPort, Protocol):
    """Reserved interface; the exported backtest never instantiates it."""

class NotImplementedBroker:
    def submit(self, orders: list[Order]) -> None:
        raise NotImplementedError("order submission is outside alphaloop v1")
'''


def build_strategy_pack(
    research: Research,
    strategy: AlphaStrategy,
    data: MarketPanel,
    destination: Path,
) -> Path:
    eligibility = strategy_pack_eligibility(research)
    if not eligibility.eligible:
        raise ValueError(f"research is not strategy-pack eligible: {eligibility.failed_checks}")
    if not isinstance(strategy, MeanReversionStrategy):
        raise TypeError("v1 exporter supports the canonical mean-reversion StrategySpec")
    if not research.versions or not research.versions[-1].rounds:
        raise ValueError("strategy pack requires a completed reviewed round")
    benchmark_prices = data.benchmark_prices
    if benchmark_prices is None:
        raise ValueError("strategy pack requires a frozen benchmark series")
    attempt = research.versions[-1].rounds[-1].accepted_attempt
    if attempt.review is None:
        raise ValueError("strategy pack requires the accepted ReviewReport")
    with TemporaryDirectory(prefix="alphaloop-pack-") as temporary:
        root = Path(temporary)
        spec = asdict(strategy.spec)
        spec["universe"]["market"] = strategy.spec.universe.market.value
        spec["universe"]["asset_class"] = strategy.spec.universe.asset_class.value
        spec["universe"]["underlying_asset_class"] = (
            strategy.spec.universe.underlying_asset_class.value
        )
        spec["method_set"] = [asdict(item) for item in strategy.spec.method_set]
        spec["benchmark_id"] = attempt.simulation.benchmark_id
        _json(root / "spec.json", spec)
        (root / "strategy.py").write_text(STRATEGY_MODULE, encoding="utf-8")
        (root / "run_backtest.py").write_text(RUNNER, encoding="utf-8")
        (root / "execution.py").write_text(EXECUTION_STUB, encoding="utf-8")
        (root / "data").mkdir()
        data.prices.to_csv(root / "data" / "prices.csv", index_label="date")
        benchmark_prices.rename("benchmark").to_csv(
            root / "data" / "benchmark.csv",
            index_label="date",
        )
        _json(root / "reports" / "metrics.json", asdict(attempt.simulation))
        _json(root / "reports" / "verification.json", asdict(attempt.verification))
        _json(root / "reports" / "review.json", asdict(attempt.review))
        _json(root / "methods" / "definitions.json", dict(VERIFIER_REVISIONS))
        sources = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in attempt.evidence_paths
        ]
        _json(root / "materials" / "sources.json", {"sources": sources})
        _json(
            root / "history" / "research.json",
            {
                "research_id": research.research_id,
                "current_version_number": research.current_version_number,
                "round_numbers": [
                    round_.number
                    for version in research.versions
                    for round_ in version.rounds
                ],
                "effective_seconds": research.effective_seconds,
            },
        )
        bundle_root = Path(
            getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
        )
        schema_source = bundle_root / "contracts" / "strategy-pack.schema.json"
        schema_target = root / "schemas" / "strategy-pack.schema.json"
        schema_target.parent.mkdir(parents=True)
        schema_target.write_bytes(schema_source.read_bytes())
        payloads = sorted(path for path in root.rglob("*") if path.is_file())
        _json(
            root / "manifest.json",
            {
                "kind": "strategy_pack",
                "schema_version": "1",
                "tradable_by_alphaloop": False,
                "research_id": research.research_id,
                "strategy_id": strategy.id,
                "files": {
                    path.relative_to(root).as_posix(): _sha256(path)
                    for path in payloads
                },
                "disclaimer": "Research artifact, not investment advice; alphaloop places no orders.",
            },
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())
    return destination
