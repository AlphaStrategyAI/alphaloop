from __future__ import annotations

from dataclasses import dataclass

from engine.research.gather import DataProfile, Material
from engine.research.models import (
    AssetClass,
    Attempt,
    ChangeClass,
    CoverageFloor,
    ImplementationDelta,
    LogicStatement,
    Market,
    MethodRef,
    Research,
    TrialCounters,
    Universe,
)
from engine.strategy import Side, StrategySpec
from engine.verifiers import method_set_excluding_pit


@dataclass(frozen=True, slots=True)
class BriefProposal:
    thesis: str
    universe: Universe
    round1_methods: tuple[MethodRef, ...]
    coverage_floor: CoverageFloor
    evidence_ids: tuple[str, ...]
    locked: bool = False


@dataclass(frozen=True, slots=True)
class ProposedChange:
    field: str
    before: object
    after: object
    breaches_coverage: bool = False


@dataclass(frozen=True, slots=True)
class ModelProposal:
    model_family: str
    lookback_days: int
    entry_z: float
    side: Side = "long_only"


def propose_brief_updates(
    message: str,
    materials: tuple[Material, ...],
    profile: DataProfile,
) -> BriefProposal:
    market = Market.US if "美股" in message or "美国" in message else Market.CN
    if any(token in message for token in ("基金", "ETF", "etf", "fund")):
        asset = AssetClass.FUND
        underlying = AssetClass.BOND if "债" in message else AssetClass.EQUITY
    elif "债" in message:
        asset = AssetClass.BOND
        underlying = AssetClass.BOND
    else:
        asset = AssetClass.EQUITY
        underlying = AssetClass.EQUITY
    universe = Universe(market, asset, underlying, profile.symbols)
    methods = (
        MethodRef("overfit.walk", "walk-v1"),
        MethodRef("stability.oos", "stability-v1"),
        MethodRef("crowding.load", "crowding-v1"),
        MethodRef("cost.turnover", "cost-v1"),
    )
    return BriefProposal(
        thesis=message.strip(),
        universe=universe,
        round1_methods=methods,
        coverage_floor=CoverageFloor(
            min_assets=len(profile.symbols),
            min_years=profile.years,
            max_missing_pct=profile.missing_pct,
        ),
        evidence_ids=tuple(item.material_id for item in materials),
    )


def classify_change(change: ProposedChange) -> ChangeClass:
    if change.breaches_coverage:
        return ChangeClass.COVERAGE
    if change.field in {
        "thesis_locked",
        "universe",
        "method_set",
        "round1_methods",
        "max_drawdown_floor",
        "validation_thresholds",
    }:
        return ChangeClass.ECONOMIC
    if change.field in {"model_family", "signal_definition", "feature_set"}:
        return ChangeClass.MODEL
    return ChangeClass.PARAM


def specify(
    research: Research,
    prior: StrategySpec | None,
    proposal: ModelProposal,
) -> StrategySpec:
    thesis = research.brief.thesis.value
    universe = research.brief.universe.value
    methods = research.brief.round1_methods.value
    if thesis is None or universe is None or methods is None:
        raise ValueError("thesis, universe, and method set must be present")
    if prior is not None and (
        prior.thesis_locked != thesis
        or prior.universe != universe
        or prior.method_set != methods
    ):
        raise ValueError("prior spec does not match locked strategy identity")
    return StrategySpec(
        id=f"{research.research_id}-{proposal.model_family}",
        thesis_locked=thesis,
        universe=universe,
        frequency="1d",
        side=proposal.side,
        method_set=methods,
        model_family=proposal.model_family,
        lookback_days=proposal.lookback_days,
        entry_z=proposal.entry_z,
        max_drawdown_floor=prior.max_drawdown_floor if prior else -0.25,
    )


def build_logic_statement(
    thesis: str,
    spec: StrategySpec,
    *,
    version_number: int,
    had_prior_round: bool,
) -> LogicStatement:
    from engine.research.display_names import MODEL_FAMILY, param_label

    family = MODEL_FAMILY.get(spec.model_family, spec.model_family)
    statement = (
        f"{thesis}（{family}，{param_label('lookback_days')}={spec.lookback_days}，"
        f"{param_label('entry_z')}={spec.entry_z}）"
    )
    return LogicStatement(
        statement=statement,
        changed_from_prior=had_prior_round,
        change_description="延续锁定论点下的参数/模型迭代" if had_prior_round else None,
        baseline_version=version_number,
    )


def build_implementation_delta(
    attempt: Attempt,
    prior_spec: StrategySpec | None,
) -> ImplementationDelta:
    spec = attempt.spec
    param_changes: list[tuple[str, str, str]] = []
    model_changes: list[str] = []
    research_changes: list[str] = []
    from engine.research.display_names import MODEL_FAMILY, method_label

    if prior_spec is None:
        if attempt.change_class is ChangeClass.MODEL:
            family = MODEL_FAMILY.get(spec.model_family, spec.model_family)
            model_changes.append(f"初始 {family} 规格")
        return ImplementationDelta(
            research_method_changes=tuple(research_changes),
            model_changes=tuple(model_changes),
            param_changes=tuple(param_changes),
        )
    if prior_spec.model_family != spec.model_family:
        before = MODEL_FAMILY.get(prior_spec.model_family, prior_spec.model_family)
        after = MODEL_FAMILY.get(spec.model_family, spec.model_family)
        model_changes.append(f"{before} → {after}")
    if prior_spec.lookback_days != spec.lookback_days:
        param_changes.append(
            ("lookback_days", str(prior_spec.lookback_days), str(spec.lookback_days))
        )
    if prior_spec.entry_z != spec.entry_z:
        param_changes.append(("entry_z", str(prior_spec.entry_z), str(spec.entry_z)))
    if attempt.change_class is ChangeClass.PARAM and not param_changes:
        param_changes.append(
            (
                "lookback_days",
                str(prior_spec.lookback_days),
                str(spec.lookback_days),
            )
        )
    method_set = method_set_excluding_pit(spec.method_set)
    if method_set:
        research_changes.append(
            "验证方法集：" + "、".join(method_label(item.method_id) for item in method_set)
        )
    return ImplementationDelta(
        research_method_changes=tuple(research_changes),
        model_changes=tuple(model_changes),
        param_changes=tuple(param_changes),
    )


def build_trial_counters(attempts: tuple[Attempt, ...], accepted: Attempt) -> TrialCounters:
    method_set = method_set_excluding_pit(accepted.spec.method_set)
    passed = sum(
        1
        for item in attempts
        if item.verification is not None and item.verification.passed_for(method_set)
    )
    return TrialCounters(
        candidates_evaluated=len(attempts),
        candidates_passed=passed,
        conclusion_attempt_number=accepted.number,
    )
