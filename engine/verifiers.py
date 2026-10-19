from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from engine.metrics import SimulationReport
from engine.research.models import Market, MethodRef


def method_set_excluding_pit(method_set: tuple[MethodRef, ...]) -> tuple[MethodRef, ...]:
    return tuple(item for item in method_set if item.method_id != "pit.consistency")
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

PIT_VERIFIER_REVISION = MappingProxyType(
    {
        "pit.consistency": {
            "revision": "pit-v1",
            "category": "时点/前视一致性",
            "dimensions": [
                {
                    "kind": "pit_consistency",
                    "name": "Point-in-Time Consistency",
                    "description": "Every evidence and backtest window uses only information available at decision time",
                    "pass_threshold": 1.0,
                    "comparison": "eq",
                    "failure_display": "Lookahead bias detected: {violations}",
                    "unit": "bool",
                }
            ],
        }
    }
)

UNKNOWN_METHOD_RULE = "unknown method revision cannot inherit a previous pass"


def unknown_revision_rule(method_id: str, revision: str) -> str:
    """Known method, unknown revision: fail closed instead of running another revision."""
    return (
        f"unknown method revision {revision} for {method_id}; "
        "refusing to fall back to another revision"
    )


@dataclass(frozen=True, slots=True)
class VerifierResult:
    verifier_id: str
    revision: str
    passed: bool
    values: Mapping[str, float]
    rule: str


PIT_REVISION_V2 = "pit-v2"
PIT_SCOPE = "只查资料发布日 ≤ 回测截止日，不覆盖标的池/复权/财务修订"
NO_EXTERNAL_EVIDENCE_NOTE = "未引用外部资料"


@dataclass(frozen=True, slots=True)
class PitViolationDetail:
    """One pit-v2 violation. Absent on pit-v1 results."""

    material_id: str
    published_at: str = ""
    title: str = ""
    precision: str = ""
    reason: str = "after_cutoff"


@dataclass(frozen=True, slots=True)
class PitVerifierResult(VerifierResult):
    """PIT consistency verification result (B1)."""
    evidence_timestamps: tuple[tuple[str, str], ...] = ()
    backtest_cutoff: str = ""
    violations: tuple[str, ...] = ()
    evidence_used: int = 0
    undated_excluded: tuple[str, ...] = ()
    scope: str = ""
    note: str = ""
    violation_details: tuple[PitViolationDetail, ...] = ()


def _pit_consistency(
    spec: StrategySpec | None,
    evidence_timestamps: list[tuple[str, str]],
    backtest_cutoff: str,
) -> PitVerifierResult:
    """Verify point-in-time consistency (B1 iron rule)."""
    del spec
    violations: list[str] = []
    cutoff_date = date.fromisoformat(backtest_cutoff)
    for evidence_id, as_of in evidence_timestamps:
        evidence_date = date.fromisoformat(as_of)
        if evidence_date > cutoff_date:
            violations.append(f"{evidence_id} dated {as_of} > cutoff {backtest_cutoff}")
    return PitVerifierResult(
        verifier_id="pit.consistency",
        revision="pit-v1",
        passed=len(violations) == 0,
        values={"violations_count": float(len(violations))},
        rule="all evidence as_of <= backtest cutoff",
        evidence_timestamps=tuple(evidence_timestamps),
        backtest_cutoff=backtest_cutoff,
        violations=tuple(violations),
    )


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


_Verifier = Callable[[SimulationReport, StrategySpec], VerifierResult]

_SELECTABLE_BY_REVISION: dict[tuple[str, str], _Verifier] = {
    ("scorecard.market", "scorecard-v1"): _scorecard,
    ("overfit.walk", "walk-v1"): _walk,
    ("stability.oos", "stability-v1"): _stability,
    ("crowding.load", "crowding-v1"): _crowding,
    ("cost.turnover", "cost-v1"): _cost,
}
_KNOWN_SELECTABLE_IDS = {method_id for method_id, _revision in _SELECTABLE_BY_REVISION}
_PIT_REVISION_V1 = "pit-v1"


def _dispatch_selectable(
    method_id: str,
    revision: str,
    report: SimulationReport,
    spec: StrategySpec,
) -> VerifierResult:
    builder = _SELECTABLE_BY_REVISION.get((method_id, revision))
    if builder is not None:
        return builder(report, spec)
    if method_id in _KNOWN_SELECTABLE_IDS:
        return VerifierResult(
            method_id,
            revision,
            False,
            {},
            unknown_revision_rule(method_id, revision),
        )
    return VerifierResult(method_id, revision, False, {}, UNKNOWN_METHOD_RULE)


def recorded_pit_revision(verification: VerificationReport | None) -> str:
    """Revision stored on the round. Missing PIT stays on v1 so old rounds are not re-judged."""
    if verification is None:
        return _PIT_REVISION_V1
    for item in verification.results:
        if item.verifier_id == "pit.consistency" and item.revision:
            return item.revision
    return _PIT_REVISION_V1


def _append_pit_result(
    results: list[VerifierResult],
    spec: StrategySpec | None,
    report: SimulationReport,
    *,
    evidence_as_of: tuple[tuple[str, str], ...],
    missing_as_of_material_ids: tuple[str, ...],
    undated_excluded: tuple[str, ...] = (),
    evidence_annotations: tuple[tuple[str, str, str], ...] = (),
    revision: str | None = None,
) -> None:
    resolved = revision or str(PIT_VERIFIER_REVISION["pit.consistency"]["revision"])
    if resolved == PIT_REVISION_V2:
        results.append(
            _pit_v2(
                spec,
                report,
                evidence_as_of=evidence_as_of,
                missing_as_of_material_ids=missing_as_of_material_ids,
                undated_excluded=undated_excluded,
                evidence_annotations=evidence_annotations,
            )
        )
        return
    if resolved != _PIT_REVISION_V1:
        results.append(
            VerifierResult(
                "pit.consistency",
                resolved,
                False,
                {},
                unknown_revision_rule("pit.consistency", resolved),
            )
        )
        return
    revision = resolved
    if report.end is None:
        results.append(
            PitVerifierResult(
                verifier_id="pit.consistency",
                revision=revision,
                passed=False,
                values={"violations_count": 1.0},
                rule="backtest cutoff required for PIT",
                evidence_timestamps=evidence_as_of,
                backtest_cutoff="",
                violations=("missing backtest cutoff",),
            )
        )
        return
    cutoff = report.end.isoformat()
    violations: list[str] = [f"{mid}: missing as_of" for mid in missing_as_of_material_ids]
    if violations:
        results.append(
            PitVerifierResult(
                verifier_id="pit.consistency",
                revision=revision,
                passed=False,
                values={"violations_count": float(len(violations))},
                rule="all evidence as_of <= backtest cutoff",
                evidence_timestamps=evidence_as_of,
                backtest_cutoff=cutoff,
                violations=tuple(violations),
            )
        )
        return
    pit = _pit_consistency(spec, list(evidence_as_of), cutoff)
    results.append(pit)


def _annotation_index(
    evidence_annotations: tuple[tuple[str, str, str], ...],
) -> dict[str, tuple[str, str]]:
    return {
        material_id: (title, precision)
        for material_id, title, precision in evidence_annotations
    }


def _pit_v2(
    spec: StrategySpec | None,
    report: SimulationReport,
    *,
    evidence_as_of: tuple[tuple[str, str], ...],
    missing_as_of_material_ids: tuple[str, ...],
    undated_excluded: tuple[str, ...],
    evidence_annotations: tuple[tuple[str, str, str], ...] = (),
) -> PitVerifierResult:
    """Same pass/fail rule as pit-v1, plus citation diagnostics."""
    del spec
    note = NO_EXTERNAL_EVIDENCE_NOTE if len(evidence_as_of) == 0 else ""
    known = _annotation_index(evidence_annotations)
    end = report.end
    if end is None:
        return PitVerifierResult(
            verifier_id="pit.consistency",
            revision=PIT_REVISION_V2,
            passed=False,
            values={"violations_count": 1.0},
            rule="backtest cutoff required for PIT",
            evidence_timestamps=evidence_as_of,
            backtest_cutoff="",
            violations=("missing backtest cutoff",),
            evidence_used=len(evidence_as_of),
            undated_excluded=undated_excluded,
            scope=PIT_SCOPE,
            note=note,
        )
    cutoff = end.isoformat()
    violations: list[str] = []
    details: list[PitViolationDetail] = []
    for material_id in missing_as_of_material_ids:
        violations.append(f"{material_id}: missing as_of")
        title, precision = known.get(material_id, ("", ""))
        details.append(
            PitViolationDetail(
                material_id=material_id,
                title=title,
                precision=precision,
                reason="missing_as_of",
            )
        )
    for evidence_id, as_of in evidence_as_of:
        if date.fromisoformat(as_of) > end:
            violations.append(f"{evidence_id} dated {as_of} > cutoff {cutoff}")
            title, precision = known.get(evidence_id, ("", ""))
            details.append(
                PitViolationDetail(
                    material_id=evidence_id,
                    published_at=as_of,
                    title=title,
                    precision=precision,
                    reason="after_cutoff",
                )
            )
    return PitVerifierResult(
        verifier_id="pit.consistency",
        revision=PIT_REVISION_V2,
        passed=len(violations) == 0,
        values={"violations_count": float(len(violations))},
        rule="all evidence as_of <= backtest cutoff",
        evidence_timestamps=evidence_as_of,
        backtest_cutoff=cutoff,
        violations=tuple(violations),
        evidence_used=len(evidence_as_of),
        undated_excluded=undated_excluded,
        scope=PIT_SCOPE,
        note=note,
        violation_details=tuple(details),
    )


def run_verifiers(
    report: SimulationReport,
    spec: StrategySpec,
    *,
    evidence_as_of: tuple[tuple[str, str], ...] = (),
    missing_as_of_material_ids: tuple[str, ...] = (),
    undated_excluded: tuple[str, ...] = (),
    evidence_annotations: tuple[tuple[str, str, str], ...] = (),
    pit_revision: str | None = None,
) -> VerificationReport:
    scorecard = _SELECTABLE_BY_REVISION[("scorecard.market", "scorecard-v1")]
    results: list[VerifierResult] = [scorecard(report, spec)]
    for item in spec.method_set:
        if item.method_id in {"scorecard.market", "pit.consistency"}:
            continue
        results.append(
            _dispatch_selectable(item.method_id, item.revision_hash, report, spec)
        )
    _append_pit_result(
        results,
        spec,
        report,
        evidence_as_of=evidence_as_of,
        missing_as_of_material_ids=missing_as_of_material_ids,
        undated_excluded=undated_excluded,
        evidence_annotations=evidence_annotations,
        revision=pit_revision,
    )
    return VerificationReport(tuple(results))
