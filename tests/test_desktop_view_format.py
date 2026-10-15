from engine.research.desktop_view import format_coverage_floor_display, format_universe_display
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
    assert format_universe_display(u) == "A股 · 债券（000001、000002）"


def test_format_coverage_floor_display():
    floor = CoverageFloor(min_assets=3, min_years=10, max_missing_pct=5)
    assert format_coverage_floor_display(floor) == (
        "至少 3 个标的、10 年数据，缺失不超过 5%"
    )
