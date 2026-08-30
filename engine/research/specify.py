from __future__ import annotations

from dataclasses import dataclass

from engine.research.gather import DataProfile, Material
from engine.research.models import (
    AssetClass,
    ChangeClass,
    CoverageFloor,
    Market,
    MethodRef,
    Research,
    Universe,
)
from engine.strategy import Side, StrategySpec


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
    asset = AssetClass.BOND if "债" in message else AssetClass.EQUITY
    methods = (
        MethodRef("overfit.walk", "walk-v1"),
        MethodRef("stability.oos", "stability-v1"),
        MethodRef("crowding.load", "crowding-v1"),
        MethodRef("cost.turnover", "cost-v1"),
    )
    return BriefProposal(
        thesis=message.strip(),
        universe=Universe(market, asset, asset, profile.symbols),
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
