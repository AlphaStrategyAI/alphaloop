from __future__ import annotations

from typing import Any

from engine.research.models import AssetClass, CoverageFloor, Market, Research, RoundV2, Universe
from engine.research.progress import _ASSET, _MARKET
from engine.research.display_names import method_label, param_label
from engine.research.round_copy import localize_logic_change, localize_model_changes
from engine.verifiers import method_set_excluding_pit

_MARKET_LABEL = _MARKET
_ASSET_LABEL = _ASSET


def format_universe_display(universe: Universe | None) -> str:
    if universe is None:
        return ""
    market = _MARKET_LABEL[universe.market]
    asset = _ASSET_LABEL[universe.asset_class]
    if universe.symbols:
        symbols = "、".join(universe.symbols)
        return f"{market} · {asset}（{symbols}）"
    return f"{market} · {asset}"


def format_coverage_vs_floor(research: Research) -> str:
    floor = research.brief.coverage_floor.value
    observed = research.last_coverage
    floor_text = format_coverage_floor_display(floor)
    if observed is None:
        return floor_text or "未锁定"
    current = (
        f"当前 {len(observed.assets)} 个标的、{observed.years:.1f} 年数据，"
        f"缺失 {observed.missing_pct:g}%"
    )
    if not floor_text:
        return current
    return f"{current}；底线 {floor_text}"


def format_coverage_floor_display(floor: CoverageFloor | None) -> str:
    if floor is None:
        return ""
    return (
        f"至少 {floor.min_assets} 个标的、"
        f"{floor.min_years:g} 年数据，缺失不超过 {floor.max_missing_pct:g}%"
    )


def universe_label_for(research: Research) -> str:
    universe = research.brief.universe.value
    if universe is None:
        return "未锁定"
    return f"{_MARKET_LABEL[universe.market]} · {_ASSET_LABEL[universe.asset_class]}"


def _pit_passed(round_: RoundV2) -> bool | None:
    verification = round_.accepted_attempt.verification
    if verification is None:
        return None
    for item in verification.results:
        if item.verifier_id == "pit.consistency":
            return item.passed
    return None


def _verification_passed(round_: RoundV2) -> bool:
    attempt = round_.accepted_attempt
    method_set = method_set_excluding_pit(attempt.spec.method_set)
    if attempt.verification is None:
        return False
    return attempt.verification.passed_for(method_set)


def _round_to_desktop(round_: RoundV2, version_number: int, idx_from_end: int) -> dict[str, Any]:
    logic = round_.logic_statement
    impl = round_.implementation_delta
    counters = round_.trial_counters
    localized_change = localize_logic_change(logic.change_description)
    model_line = localize_model_changes(impl.model_changes)
    return {
        "roundId": round_.round_id,
        "number": round_.number,
        "logicStatement": {
            "statement": logic.statement,
            "changedFromPrior": logic.changed_from_prior,
            "changeDescription": localized_change or logic.change_description,
            "baselineVersion": logic.baseline_version or version_number,
        },
        "implementationDelta": {
            "researchMethodChanges": list(impl.research_method_changes),
            "modelChanges": list(impl.model_changes),
            "modelChangesDisplay": model_line or None,
            "paramChanges": [
                [param_label(param), str(before), str(after)]
                for param, before, after in impl.param_changes
            ],
        },
        "trialCounters": {
            "candidatesEvaluated": counters.candidates_evaluated,
            "candidatesPassed": counters.candidates_passed,
            "conclusionAttemptNumber": counters.conclusion_attempt_number,
        },
        "verificationPassed": _verification_passed(round_),
        "pitPassed": _pit_passed(round_),
        "indexFromEnd": idx_from_end,
    }


def rounds_for_desktop(research: Research, version_number: int) -> list[dict[str, Any]]:
    if not research.versions or version_number < 1:
        return []
    rounds = research.versions[version_number - 1].rounds
    ordered = list(reversed(rounds))
    return [
        _round_to_desktop(round_, version_number, idx)
        for idx, round_ in enumerate(ordered)
    ]


def selected_method_id(research: Research) -> str:
    if not research.versions or not research.versions[-1].rounds:
        return ""
    spec = research.versions[-1].rounds[-1].accepted_attempt.spec
    for item in method_set_excluding_pit(spec.method_set):
        if item.method_id != "scorecard.market":
            return item.method_id
    return ""


def reverify_options_for(research: Research) -> dict[str, Any]:
    if not research.versions:
        return {"rounds": []}
    version_number = research.current_version_number or 1
    version = research.versions[version_number - 1]
    rounds_out: list[dict[str, Any]] = []
    for round_ in version.rounds:
        verification = round_.accepted_attempt.verification
        if verification is None:
            continue
        methods = [
            {
                "methodId": item.verifier_id,
                "methodLabel": method_label(item.verifier_id),
            }
            for item in verification.results
        ]
        rounds_out.append(
            {
                "roundId": round_.round_id,
                "roundLabel": f"第 {round_.number} 轮",
                "methods": methods,
            }
        )
    return {"rounds": rounds_out}


def last_reverification_summary(research: Research) -> dict[str, Any] | None:
    if not research.reverifications:
        return None
    last = research.reverifications[-1]
    return {
        "roundId": last.round_id,
        "methodId": last.method_id,
        "methodLabel": method_label(last.method_id),
        "passed": last.passed,
        "createdAt": last.created_at.isoformat(),
    }


def metrics_for_completed(research: Research) -> dict[str, Any] | None:
    if not research.versions or not research.versions[-1].rounds:
        return None
    simulation = research.versions[-1].rounds[-1].accepted_attempt.simulation
    if simulation is None:
        return None
    return {
        "sharpe": getattr(simulation, "sharpe", None),
        "sharpeOos": getattr(simulation, "sharpe_oos", None),
        "excessAnn": getattr(simulation, "excess_ann", None),
        "maxDrawdown": getattr(simulation, "max_drawdown", None),
    }
