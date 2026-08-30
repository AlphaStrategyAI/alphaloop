from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from engine.metrics import SimulationReport
from engine.research.models import Market
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

    @property
    def passed(self) -> bool:
        return len(self.results) == 5 and all(result.passed for result in self.results)


def run_verifiers(report: SimulationReport, spec: StrategySpec) -> VerificationReport:
    scorecard = VerifierResult(
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
    ratio = 0.0 if report.sharpe_is == 0.0 else report.sharpe_oos / report.sharpe_is
    walk = VerifierResult(
        "overfit.walk",
        "walk-v1",
        report.sharpe_oos > 0 and ratio >= 0.6,
        {"sharpe_oos": report.sharpe_oos, "oos_to_is": ratio},
        "sharpe_oos > 0 and sharpe_oos / sharpe_is >= 0.6",
    )
    segments = report.oos_segment_returns

    def sign(value: float) -> int:
        return (value > 0) - (value < 0)

    first_sign = sign(segments[0]) if segments else 0
    same_sign_ratio = (
        sum(sign(value) == first_sign for value in segments) / len(segments)
        if segments
        else 0.0
    )
    stability = VerifierResult(
        "stability.oos",
        "stability-v1",
        len(segments) >= 3 and same_sign_ratio >= 2 / 3,
        {"segments": float(len(segments)), "same_sign_ratio": same_sign_ratio},
        "at least 3 OOS segments and same-sign ratio >= 2/3",
    )
    crowding = VerifierResult(
        "crowding.load",
        "crowding-v1",
        report.top_20_crowding_sharpe_impact >= 0,
        {"top_20_crowding_sharpe_impact": report.top_20_crowding_sharpe_impact},
        "top 20% crowding bucket sharpe impact >= 0",
    )
    cost_bp = 10 if spec.universe.market is Market.US else 20
    cost_drag = report.annual_turnover * cost_bp / 10_000
    net_excess = report.excess_ann - cost_drag
    cost = VerifierResult(
        "cost.turnover",
        "cost-v1",
        net_excess > 0,
        {"cost_drag": cost_drag, "net_excess_ann": net_excess},
        "excess_ann - annual_turnover * market_cost_bp / 10000 > 0",
    )
    return VerificationReport((scorecard, walk, stability, crowding, cost))
