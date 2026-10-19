from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from engine.research.glossary import write_glossary
from engine.research.models import (
    Attempt,
    Research,
    ResearchStatus,
    RoundV2,
)
from engine.research.thesis_scope import export_thesis_markers
from engine.strategy import AlphaStrategy, MarketPanel, MeanReversionStrategy
from engine.verifiers import (
    PitVerifierResult,
    VERIFIER_REVISIONS,
    VerifierResult,
    method_set_excluding_pit,
)


@dataclass(frozen=True, slots=True)
class ExportEligibility:
    eligible: bool
    failed_checks: tuple[str, ...]


def _pit_verification_payload(pit_result: VerifierResult | None) -> dict[str, object]:
    payload: dict[str, object] = {
        "executed": pit_result is not None,
        "passed": pit_result is not None and pit_result.passed,
        "violations": list(pit_result.violations) if isinstance(pit_result, PitVerifierResult) else [],
    }
    if isinstance(pit_result, PitVerifierResult):
        payload["evidence_used"] = pit_result.evidence_used
        payload["undated_excluded"] = list(pit_result.undated_excluded)
        payload["scope"] = pit_result.scope
        if pit_result.note:
            payload["note"] = pit_result.note
    return payload


def _material_sources(paths: tuple[Path, ...]) -> dict[str, object]:
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    return {
        "sources": rows,
        "used": [row for row in rows if row.get("published_at")],
        "browsed_not_used": [row for row in rows if not row.get("published_at")],
    }


def _find_pit_result(attempt: Attempt) -> VerifierResult | None:
    """Find PIT verifier result in attempt's verification report."""
    if attempt.verification is None:
        return None
    for result in attempt.verification.results:
        if result.verifier_id == "pit.consistency":
            return result  # type: ignore[no-any-return]
    return None


def _round_history_with_trials(
    research: Research,
    rounds: list[RoundV2],
) -> dict[str, object]:
    """Export round history with B2/B3 trial counts, logic/impl split, and cumulative M."""
    from engine.research.data_window import (
        anchor_data_window_key,
        cumulative_rounds_on_window,
        data_window_key_from_round,
        rounds_on_window_chronological,
    )

    anchor = anchor_data_window_key(research)
    on_window = rounds_on_window_chronological(research)
    cumulative_index = {
        round_.round_id: index for index, (_, round_) in enumerate(on_window, start=1)
    }
    from engine.research.data_window import data_window_key_from_research

    pinned = data_window_key_from_research(research)
    return {
        "data_window_key": anchor.serialize() if anchor else None,
        "symbol_list_version": research.symbol_list_version,
        "data_source_id": research.data_source_id,
        "data_window_start": (
            research.data_window_start.isoformat() if research.data_window_start else None
        ),
        "data_window_end": (
            research.data_window_end.isoformat() if research.data_window_end else None
        ),
        "cumulative_rounds_on_window": cumulative_rounds_on_window(research),
        "rounds": [
        {
            "round_id": round_.round_id,
            "number": round_.number,
            "cumulative_round_on_window": cumulative_index.get(round_.round_id),
            "data_window_key": (
                data_window_key_from_round(round_, research).serialize()
                if data_window_key_from_round(round_, research) is not None
                else None
            ),
            "logic_statement": {
                "statement": round_.logic_statement.statement,
                "changed_from_prior": round_.logic_statement.changed_from_prior,
                "change_description": round_.logic_statement.change_description,
                "baseline_version": round_.logic_statement.baseline_version,
            },
            "implementation_delta": {
                "research_method_changes": list(round_.implementation_delta.research_method_changes),
                "model_changes": list(round_.implementation_delta.model_changes),
                "param_changes": [list(p) for p in round_.implementation_delta.param_changes],
            },
            "trial_counters": {
                "candidates_evaluated": round_.trial_counters.candidates_evaluated,
                "candidates_passed": round_.trial_counters.candidates_passed,
                "conclusion_attempt_number": round_.trial_counters.conclusion_attempt_number,
            },
        }
        for round_ in rounds
        ],
    }


def strategy_pack_eligibility(research: Research) -> ExportEligibility:
    """Four-condition eligibility check (B1 adds fourth gate)."""
    current_attempt = (
        research.versions[-1].rounds[-1].accepted_attempt
        if research.versions and research.versions[-1].rounds
        else None
    )
    pit_result = _find_pit_result(current_attempt) if current_attempt else None
    current_round_id = (
        research.versions[-1].rounds[-1].round_id
        if research.versions and research.versions[-1].rounds
        else None
    )
    method_set = ()
    if current_attempt is not None and current_attempt.spec is not None:
        method_set = method_set_excluding_pit(current_attempt.spec.method_set)
    methods_passed = (
        current_attempt is not None
        and current_attempt.verification is not None
        and current_attempt.verification.passed_for(method_set)
    )
    checks = {
        "completed": research.status is ResearchStatus.COMPLETED,
        "all_current_methods_passed": methods_passed,
        "no_pending_confirm": research.pending_confirm is None,
        "all_reverifies_passed": all(
            reverification.passed
            for reverification in research.reverifications
            if current_round_id is not None
            and reverification.round_id == current_round_id
            and reverification.method_id != "pit.consistency"
        ),
        "pit_executed_and_passed": pit_result is not None and pit_result.passed,
    }
    return ExportEligibility(
        eligible=all(checks.values()),
        failed_checks=tuple(name for name, passed in checks.items() if not passed),
    )


def _provenance_cutoff(research: Research) -> str | None:
    if research.last_coverage is not None:
        return research.last_coverage.end.isoformat()
    if research.coverage_history:
        return research.coverage_history[-1].after.end.isoformat()
    if research.versions and research.versions[-1].rounds:
        simulation = research.versions[-1].rounds[-1].accepted_attempt.simulation
        end = getattr(simulation, "end", None)
        if end is not None and hasattr(end, "isoformat"):
            return str(end.isoformat())
    return None


def importer_accepts(manifest: dict[str, object]) -> bool:
    return (
        manifest.get("kind") == "strategy_pack"
        and manifest.get("live_handoff_eligible") is True
    )


def mark_exports_overturned(research: Research) -> Research:
    return replace(
        research,
        export_eligible=False,
        exports=tuple(replace(item, overturned=True) for item in research.exports),
    )


def _frozen_benchmark(data: MarketPanel) -> pd.Series:
    if data.benchmark_prices is not None:
        return data.benchmark_prices
    observed = data.observed_at
    if isinstance(observed, pd.Series):
        return observed
    if "__benchmark__" in data.prices.columns:
        return data.prices["__benchmark__"]
    raise ValueError("strategy pack requires a frozen benchmark series")


def _asset_prices(data: MarketPanel) -> pd.DataFrame:
    if "__benchmark__" in data.prices.columns:
        return data.prices.drop(columns=["__benchmark__"])
    return data.prices


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


def _one_way_cost(spec):
    market = spec["universe"]["market"]
    asset = spec["universe"]["asset_class"]
    if market == "US" and asset == "fund":
        return 1.0 / 10000.0
    if market == "US" and asset == "equity":
        return 5.0 / 10000.0
    if market == "CN" and asset == "equity":
        return 20.0 / 10000.0
    if market == "CN" and asset == "fund":
        return 5.0 / 10000.0
    return 0.0


def _clip_redistribute(raw, cap):
    weights = [max(value, 0.0) for value in raw]
    total = sum(weights)
    if total <= 0.0:
        return weights
    if total > 1.0:
        weights = [value / total for value in weights]
    for _ in range(len(weights) + 1):
        over = [value > cap + 1e-15 for value in weights]
        if not any(over):
            break
        excess = sum(weights[index] - cap for index, flagged in enumerate(over) if flagged)
        for index, flagged in enumerate(over):
            if flagged:
                weights[index] = cap
        room = [0.0 if over[index] else max(cap - weights[index], 0.0) for index in range(len(weights))]
        room_sum = sum(room)
        if room_sum <= 1e-15:
            break
        weights = [weights[index] + room[index] * (excess / room_sum) for index in range(len(weights))]
    total = sum(weights)
    if total > 1.0 + 1e-15:
        weights = [value / total for value in weights]
    return weights


def _allocate_row(signal, score, symbols, cap):
    if not cap:
        gross = sum(abs(signal[symbol]) for symbol in symbols) or 1.0
        return {symbol: signal[symbol] / gross for symbol in symbols}
    active = [symbol for symbol in symbols if signal[symbol] > 0.0]
    if not active:
        return {symbol: 0.0 for symbol in symbols}
    magnitudes = [abs(signal[symbol]) for symbol in active]
    equal = max(magnitudes) - min(magnitudes) <= 1e-12
    if not equal:
        raw = [abs(signal[symbol]) if signal[symbol] > 0.0 else 0.0 for symbol in symbols]
        clipped = _clip_redistribute(raw, cap)
        return {symbol: clipped[index] for index, symbol in enumerate(symbols)}
    chosen = list(active)
    if (1.0 / len(chosen)) > cap:
        order = sorted(
            symbols,
            key=lambda symbol: (
                0 if score[symbol] == score[symbol] else 1,
                -(score[symbol] if score[symbol] == score[symbol] else 0.0),
                symbols.index(symbol),
            ),
        )
        for symbol in order:
            if symbol in chosen or score[symbol] != score[symbol]:
                continue
            chosen.append(symbol)
            if (1.0 / len(chosen)) <= cap:
                break
    weight = 1.0 / len(chosen)
    if weight > cap:
        weight = cap
    return {symbol: weight if symbol in chosen else 0.0 for symbol in symbols}


def _scheduled_returns(signals, zscores, asset_returns, symbols, cap, rate):
    strategy_returns = []
    previous = {symbol: 0.0 for symbol in symbols}
    for index in range(len(signals)):
        lagged_signal = signals[index - 1] if index else {symbol: 0.0 for symbol in symbols}
        lagged_score = zscores[index - 1] if index else {symbol: 0.0 for symbol in symbols}
        weights = _allocate_row(lagged_signal, lagged_score, symbols, cap)
        gross = sum(weights[symbol] * (asset_returns[symbol][index] or 0.0) for symbol in symbols)
        turnover = sum(abs(weights[symbol] - previous[symbol]) for symbol in symbols)
        strategy_returns.append(gross - turnover * rate)
        previous = weights
    return strategy_returns


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
    zscores = []
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
            zscores.append({symbol: 0.0 for symbol in symbols})
            continue
        dispersion = statistics.stdev(scores.values()) if len(scores) > 1 else 0.0
        center = statistics.mean(scores.values())
        row = {}
        zrow = {}
        for symbol, score in scores.items():
            zscore = 0.0 if dispersion == 0.0 else (score - center) / dispersion
            zrow[symbol] = zscore
            row[symbol] = (
                1.0
                if zscore >= entry_z
                else -1.0
                if spec["side"] == "long_short" and zscore <= -entry_z
                else 0.0
            )
        signals.append(row)
        zscores.append(zrow)
    cap = spec.get("name_weight_cap")
    if spec.get("cost_model") == "schedule_v1":
        strategy_returns = _scheduled_returns(
            signals,
            zscores,
            asset_returns,
            symbols,
            float(cap) if cap else None,
            _one_way_cost(spec),
        )
    else:
        strategy_returns = []
        for index in range(len(rows)):
            prior = signals[index - 1] if index > 0 else {symbol: 0.0 for symbol in symbols}
            gross = sum(abs(value) for value in prior.values()) or 1.0
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
    benchmark_prices = _frozen_benchmark(data)
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
        spec.update(export_thesis_markers(strategy.spec.thesis_locked))
        _json(root / "spec.json", spec)
        (root / "strategy.py").write_text(STRATEGY_MODULE, encoding="utf-8")
        (root / "run_backtest.py").write_text(RUNNER, encoding="utf-8")
        (root / "execution.py").write_text(EXECUTION_STUB, encoding="utf-8")
        (root / "data").mkdir()
        _asset_prices(data).to_csv(root / "data" / "prices.csv", index_label="date")
        benchmark_prices.rename("benchmark").to_csv(
            root / "data" / "benchmark.csv",
            index_label="date",
        )
        _json(root / "reports" / "metrics.json", asdict(attempt.simulation))
        _json(root / "reports" / "verification.json", asdict(attempt.verification))
        _json(root / "reports" / "review.json", asdict(attempt.review))
        _json(root / "methods" / "definitions.json", dict(VERIFIER_REVISIONS))
        sources_payload = _material_sources(attempt.evidence_paths)
        sources = sources_payload["sources"]
        _json(root / "materials" / "sources.json", sources_payload)
        _json(
            root / "data" / "provenance.json",
            {
                "sources": sources,
                "assets": list(strategy.spec.universe.symbols),
                "coverage_floor": asdict(research.brief.coverage_floor.value)
                if research.brief.coverage_floor.value
                else None,
                "shrinks": [asdict(item) for item in research.coverage_history],
                "cutoff": _provenance_cutoff(research),
            },
        )
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
                **export_thesis_markers(strategy.spec.thesis_locked),
            },
        )
        all_rounds = [
            round_
            for version in research.versions
            for round_ in version.rounds
        ]
        _json(
            root / "history" / "rounds.json",
            _round_history_with_trials(research, all_rounds),
        )
        write_glossary(root)
        bundle_root = Path(
            getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
        )
        schema_source = bundle_root / "contracts" / "strategy-pack.schema.json"
        schema_target = root / "schemas" / "strategy-pack.schema.json"
        schema_target.parent.mkdir(parents=True)
        schema_target.write_bytes(schema_source.read_bytes())
        pit_result = _find_pit_result(attempt)
        pit_verification = _pit_verification_payload(pit_result)
        payloads = sorted(path for path in root.rglob("*") if path.is_file())
        _json(
            root / "manifest.json",
            {
                "kind": "strategy_pack",
                "schema_version": "1",
                "live_handoff_eligible": True,
                "tradable_by_alphaloop": False,
                "research_id": research.research_id,
                "strategy_id": strategy.id,
                "files": {
                    path.relative_to(root).as_posix(): _sha256(path)
                    for path in payloads
                },
                "disclaimer": "Research artifact, not investment advice; alphaloop places no orders.",
                "pit_verification": pit_verification,
            },
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())
    return destination


def _record_thesis(research: Research) -> str:
    brief = research.brief.thesis.value
    if isinstance(brief, str) and brief:
        return brief
    for version in reversed(research.versions):
        for round_ in reversed(version.rounds):
            spec = round_.accepted_attempt.spec
            if spec is not None and spec.thesis_locked:
                return spec.thesis_locked
    return ""


def build_research_record_pack(research: Research, destination: Path) -> Path:
    eligibility = strategy_pack_eligibility(research)
    with TemporaryDirectory(prefix="alphaloop-record-") as temporary:
        root = Path(temporary)
        _json(
            root / "history" / "research.json",
            {
                "research_id": research.research_id,
                "status": research.status.value,
                "current_version_number": research.current_version_number,
                "round_numbers": [
                    round_.number
                    for version in research.versions
                    for round_ in version.rounds
                ],
                "effective_seconds": research.effective_seconds,
                "export_eligible": research.export_eligible,
                **export_thesis_markers(_record_thesis(research)),
            },
        )
        if research.last_run_error:
            recorded = json.loads((root / "history" / "research.json").read_text(encoding="utf-8"))
            recorded["last_run_error"] = research.last_run_error
            if research.last_run_error_code:
                recorded["last_run_error_code"] = research.last_run_error_code
            _json(root / "history" / "research.json", recorded)
        all_rounds = [round_ for version in research.versions for round_ in version.rounds]
        from engine.research.data_window import (
            cumulative_rounds_on_window,
            data_window_key_from_round,
            rounds_on_window_chronological,
        )

        cumulative_m = cumulative_rounds_on_window(research)
        cumulative_index = {
            round_.round_id: index
            for index, (_, round_) in enumerate(
                rounds_on_window_chronological(research),
                start=1,
            )
        }
        _json(
            root / "history" / "rounds.json",
            _round_history_with_trials(research, all_rounds),
        )
        _json(
            root / "history" / "verification_attempts.json",
            [
                {
                    "round_id": round_.round_id,
                    "attempt_id": round_.accepted_attempt.attempt_id,
                    "data_window_key": (
                        data_window_key_from_round(round_, research).serialize()
                        if data_window_key_from_round(round_, research) is not None
                        else None
                    ),
                    "cumulative_rounds_on_window": cumulative_m,
                    "cumulative_round_on_window": cumulative_index.get(round_.round_id),
                    "verification": asdict(round_.accepted_attempt.verification),
                }
                for version in research.versions
                for round_ in version.rounds
            ],
        )
        _json(
            root / "history" / "reverifications.json",
            [asdict(item) for item in research.reverifications],
        )
        latest_attempt = (
            research.versions[-1].rounds[-1].accepted_attempt
            if research.versions and research.versions[-1].rounds
            else None
        )
        pit_payload = _pit_verification_payload(
            _find_pit_result(latest_attempt) if latest_attempt is not None else None
        )
        _json(root / "history" / "pit_verification.json", pit_payload)
        why_not_live: dict[str, object] = {"failed_checks": list(eligibility.failed_checks)}
        scope = pit_payload.get("scope")
        if isinstance(scope, str) and scope:
            why_not_live["pit_scope"] = scope
        _json(
            root / "why_not_live.json",
            why_not_live,
        )
        write_glossary(root)
        bundle_root = Path(
            getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
        )
        schema_source = bundle_root / "contracts" / "research-record.schema.json"
        schema_target = root / "schemas" / "research-record.schema.json"
        schema_target.parent.mkdir(parents=True)
        schema_target.write_bytes(schema_source.read_bytes())
        _json(
            root / "manifest.json",
            {
                "kind": "research_record",
                "schema_version": "1",
                "live_handoff_eligible": False,
                "research_id": research.research_id,
                "disclaimer": (
                    "Research record only; not a live-handoff strategy pack. "
                    "alphaloop places no orders."
                ),
            },
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())
    return destination
