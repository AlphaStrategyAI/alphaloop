from engine.research.desktop_view import (
    format_coverage_floor_display,
    format_coverage_vs_floor,
    format_universe_display,
)
from engine.research.models import CoverageFloor, CoverageSnapshot
from engine.research.models import new_research
from datetime import UTC, date, datetime
from engine.research.models import AssetClass, CoverageFloor, Market, Universe


def test_format_universe_display_without_symbols():
    u = Universe(
        market=Market.US,
        asset_class=AssetClass.EQUITY,
        underlying_asset_class=AssetClass.EQUITY,
        symbols=(),
    )
    assert format_universe_display(u) == "美股 · 股票"


def test_format_universe_display_with_symbols():
    u = Universe(
        market=Market.CN,
        asset_class=AssetClass.BOND,
        underlying_asset_class=AssetClass.BOND,
        symbols=("000001", "000002"),
    )
    assert format_universe_display(u) == "A 股 · 债券（000001、000002）"


def test_format_coverage_vs_floor_uses_readable_floor_not_repr() -> None:
    research = new_research("r-fmt", datetime(2026, 1, 1, tzinfo=UTC))
    from dataclasses import replace

    from engine.research.models import ResearchBrief, Slot

    brief = replace(
        research.brief,
        coverage_floor=Slot(CoverageFloor(1, 5, 20.0), True),
    )
    research = replace(
        research,
        brief=brief,
        last_coverage=CoverageSnapshot(
            ("SPY",),
            5.0,
            0.0,
            date(2020, 1, 1),
            date(2025, 1, 1),
            datetime(2026, 1, 1, tzinfo=UTC),
        ),
    )
    text = format_coverage_vs_floor(research)
    assert "至少 1 个标的" in text
    assert "CoverageFloor" not in text


def test_format_coverage_floor_display():
    floor = CoverageFloor(min_assets=3, min_years=10, max_missing_pct=5)
    assert format_coverage_floor_display(floor) == (
        "至少 3 个标的、10 年数据，缺失不超过 5%"
    )
