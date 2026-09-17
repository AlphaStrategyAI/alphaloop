from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from engine.metrics import SimulationReport
from engine.research.models import Market, MethodRef
from engine.strategy import StrategySpec

VERIFIER_REVISIONS = MappingProxyType(
    {
        "scorecard.market": {
            "revision": "scorecard-v1",
            "sharpe_oos_min_exclusive": 0.0,
            "excess_ann_min_exclusive": 0.0,
            "default_max_drawdown_floor": -0.25,
        },
        "overfit.walk": {
            "revision": "walk-v1",
            "n_splits": 5,
            "oos_to_is_min": 0.6,
            "sharpe_oos_min_exclusive": 0.0,
        },
        "stability.oos": {
            "revision": "stability-v1",
            "segments_min": 3,
            "same_sign_ratio_min": 2 / 3,
        },
        "crowding.load": {
            "revision": "crowding-v1",
            "top_bucket_pct": 20,
            "sharpe_impact_min": 0.0,
        },
        "cost.turnover": {
            "revision": "cost-v1",
            "us_cost_bp": 10,
            "cn_cost_bp": 20,
            "net_excess_min_exclusive": 0.0,
        },
    }
)

UNKNOWN_METHOD_RULE = "unknown method revision cannot inherit a previous pass"


@dataclass(frozen=True, slots=True)
class VerifierResult:
    verifier_id: str
    revision: str
    passed: bool
    values: Mapping[str, float]
    rule: str


@dataclass(frozen=True, slots=True)
class VerificationReport:
    results: tuple[VerifierResult, ...]

    def passed_for(self, method_set: tuple[MethodRef, ...]) -> bool:
        required = {"scorecard.market", *(item.method_id for item in method_set)}
        by_id = {item.verifier_id: item for item in self.results}
        return all(name in by_id and by_id[name].passed for name in required)

    @property
    def passed(self) -> bool:
        required = {item.verifier_id for item in self.results}
        return (
            bool(self.results)
            and all(item.passed for item in self.results)
            and "scorecard.market" in required
        )


def _scorecard(report: SimulationReport, spec: StrategySpec) -> VerifierResult:
    return VerifierResult(
        "scorecard.market",
        "scorecard-v1",
        report.sharpe_oos > 0
        and report.excess_ann > 0
        and report.max_drawdown >= spec.max_drawdown_floor,
        {
            "sharpe_oos": report.sharpe_oos,
            "excess_ann": report.excess_ann,
            "max_drawdown": report.max_drawdown,
            "max_drawdown_floor": spec.max_drawdown_floor,
        },
        "sharpe_oos > 0 and excess_ann > 0 and max_drawdown >= max_drawdown_floor",
    )


def _walk(report: SimulationReport, spec: StrategySpec) -> VerifierResult:
    del spec
    ratio = 0.0 if report.sharpe_is == 0.0 else report.sharpe_oos / report.sharpe_is
    return VerifierResult(
        "overfit.walk",
        "walk-v1",
        report.sharpe_oos > 0 and ratio >= 0.6,
        {"sharpe_oos": report.sharpe_oos, "oos_to_is": ratio},
        "sharpe_oos > 0 and sharpe_oos / sharpe_is >= 0.6",
    )


def _stability(report: SimulationReport, spec: StrategySpec) -> VerifierResult:
    del spec
    segments = report.oos_segment_returns

    def sign(value: float) -> int:
        return (value > 0) - (value < 0)

    first_sign = sign(segments[0]) if segments else 0
    same_sign_ratio = (
        sum(sign(value) == first_sign for value in segments) / len(segments) if segments else 0.0
    )
    return VerifierResult(
        "stability.oos",
        "stability-v1",
        len(segments) >= 3 and same_sign_ratio >= 2 / 3,
        {"segments": float(len(segments)), "same_sign_ratio": same_sign_ratio},
        "at least 3 OOS segments and same-sign ratio >= 2/3",
    )


def _crowding(report: SimulationReport, spec: StrategySpec) -> VerifierResult:
    del spec
    return VerifierResult(
        "crowding.load",
        "crowding-v1",
        report.top_20_crowding_sharpe_impact >= 0,
        {"top_20_crowding_sharpe_impact": report.top_20_crowding_sharpe_impact},
        "top 20% crowding bucket sharpe impact >= 0",
    )


def _cost(report: SimulationReport, spec: StrategySpec) -> VerifierResult:
    cost_bp = 10 if spec.universe.market is Market.US else 20
    cost_drag = report.annual_turnover * cost_bp / 10_000
    net_excess = report.excess_ann - cost_drag
    return VerifierResult(
        "cost.turnover",
        "cost-v1",
        net_excess > 0,
        {"cost_drag": cost_drag, "net_excess_ann": net_excess},
        "excess_ann - annual_turnover * market_cost_bp / 10000 > 0",
    )


_SELECTABLE: dict[str, Callable[[SimulationReport, StrategySpec], VerifierResult]] = {
    "overfit.walk": _walk,
    "stability.oos": _stability,
    "crowding.load": _crowding,
    "cost.turnover": _cost,
}


def run_verifiers(report: SimulationReport, spec: StrategySpec) -> VerificationReport:
    results = [_scorecard(report, spec)]
    for item in spec.method_set:
        if item.method_id == "scorecard.market":
            continue
        builder = _SELECTABLE.get(item.method_id)
        if builder is None:
            results.append(
                VerifierResult(
                    item.method_id,
                    item.revision_hash,
                    False,
                    {},
                    UNKNOWN_METHOD_RULE,
                )
            )
            continue
        results.append(builder(report, spec))
    return VerificationReport(tuple(results))
