from dataclasses import replace
from datetime import UTC, datetime

import pytest

from engine.research.gather import DataProfile, Material, MaterialPort, gather
from engine.research.models import (
    AssetClass,
    ChangeClass,
    CoverageFloor,
    Market,
    MethodRef,
    ResearchBrief,
    Slot,
    Universe,
    new_research,
)
from engine.research.specify import (
    ModelProposal,
    ProposedChange,
    classify_change,
    propose_brief_updates,
    specify,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


class FakeMaterials(MaterialPort):
    def __init__(self, source: str) -> None:
        self.source = source

    def fetch(self, query: str) -> tuple[Material, ...]:
        return (
            Material(
                material_id=f"{self.source}-1",
                source=self.source,
                title=f"{query} factor evidence",
                url=f"https://example.test/{self.source}",
                text="Low-volatility reversal should be tested out of sample and for crowding.",
                fetched_at=NOW,
            ),
        )


def locked_research():
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAPL", "MSFT"))
    brief = ResearchBrief(
        thesis=Slot("美股低波动回归", True),
        universe=Slot(universe, True),
        max_effective_hours=Slot(12.0, True),
        round1_methods=Slot(
            (
                MethodRef("overfit.walk", "walk-v1"),
                MethodRef("stability.oos", "stability-v1"),
                MethodRef("crowding.load", "crowding-v1"),
                MethodRef("cost.turnover", "cost-v1"),
            ),
            True,
        ),
        coverage_floor=Slot(CoverageFloor(2, 10, 5.0), True),
    )
    return replace(new_research("r-spec", NOW), brief=brief)


def test_gather_keeps_public_source_provenance() -> None:
    result = gather("美股低波动回归", (FakeMaterials("papers"), FakeMaterials("sec-edgar")))
    assert [item.source for item in result] == ["papers", "sec-edgar"]
    assert all(item.url.startswith("https://") for item in result)


def test_materials_and_data_profile_propose_values_without_locking() -> None:
    materials = gather("美股低波动回归", (FakeMaterials("papers"),))
    proposal = propose_brief_updates(
        "美股低波动回归",
        materials,
        DataProfile(symbols=("AAPL", "MSFT"), years=12, missing_pct=1.5),
    )
    assert proposal.universe.market is Market.US
    assert proposal.universe.asset_class is AssetClass.EQUITY
    assert [item.method_id for item in proposal.round1_methods] == [
        "overfit.walk",
        "stability.oos",
        "crowding.load",
        "cost.turnover",
    ]
    assert proposal.coverage_floor == CoverageFloor(2, 12, 1.5)
    assert proposal.locked is False


@pytest.mark.parametrize(
    ("change", "expected"),
    (
        (ProposedChange("lookback_days", 20, 30), ChangeClass.PARAM),
        (ProposedChange("signal_definition", "zscore", "rank"), ChangeClass.MODEL),
        (ProposedChange("thesis_locked", "reversion", "momentum"), ChangeClass.ECONOMIC),
        (ProposedChange("universe", "US equity", "CN equity"), ChangeClass.ECONOMIC),
        (ProposedChange("method_set", "walk-v1", "walk-v2"), ChangeClass.ECONOMIC),
        (ProposedChange("max_drawdown_floor", -0.25, -0.30), ChangeClass.ECONOMIC),
        (ProposedChange("available_assets", 50, 40, breaches_coverage=True), ChangeClass.COVERAGE),
    ),
)
def test_change_classifier(change: ProposedChange, expected: ChangeClass) -> None:
    assert classify_change(change) is expected


def test_specify_preserves_locked_thesis_universe_and_methods() -> None:
    research = locked_research()
    first = specify(research, None, ModelProposal("mean_reversion", 20, 1.0, "long_only"))
    second = specify(research, first, ModelProposal("mean_reversion", 30, 0.8, "long_only"))
    assert second.thesis_locked == first.thesis_locked
    assert second.universe == first.universe
    assert second.method_set == first.method_set
    assert second.lookback_days == 30


def test_specify_rejects_a_prior_spec_from_another_economic_version() -> None:
    research = locked_research()
    first = specify(research, None, ModelProposal("mean_reversion", 20, 1.0, "long_only"))
    foreign = replace(first, thesis_locked="momentum")
    with pytest.raises(ValueError, match="locked strategy identity"):
        specify(research, foreign, ModelProposal("mean_reversion", 30, 0.8, "long_only"))
