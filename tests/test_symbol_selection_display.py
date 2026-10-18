from dataclasses import replace
from datetime import UTC, datetime

from engine.research.confirm_view import symbol_selection_payload
from engine.research.models import (
    AssetClass,
    CoverageFloor,
    Market,
    ResearchBrief,
    Slot,
    Universe,
    new_research,
)
from engine.research.symbol_selection_display import format_symbol_selection_summary

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _research_with_pool() -> object:
    brief = ResearchBrief(
        thesis=Slot("均值回归", True),
        universe=Slot(
            Universe(
                market=Market.US,
                asset_class=AssetClass.EQUITY,
                underlying_asset_class=AssetClass.EQUITY,
                symbols=(),
            ),
            True,
        ),
        max_effective_hours=Slot(3.0, True),
        round1_methods=Slot((), True),
        coverage_floor=Slot(CoverageFloor(5, 3.0, 5.0), True),
    )
    return replace(new_research("r-1", NOW), brief=brief)


def test_symbol_selection_summary_line_once_lists_pool_name() -> None:
    payload = symbol_selection_payload(_research_with_pool())
    assert payload is not None
    line = format_symbol_selection_summary(payload)
    assert payload["summaryLine"] == line
    assert line == "40 只 · 美股大市值 · 版本 1 · 2026-10-17 · 默认标的池"
    assert line.count("美股大市值") == 1
    assert "版本 1" in line
    assert "（版本 1）" not in line


def test_user_override_note_copy() -> None:
    brief = ResearchBrief(
        thesis=Slot("A股回归", True),
        universe=Slot(
            Universe(
                market=Market.CN,
                asset_class=AssetClass.EQUITY,
                underlying_asset_class=AssetClass.EQUITY,
                symbols=("600519.SH",),
                user_symbols_override=True,
            ),
            True,
        ),
        max_effective_hours=Slot(3.0, True),
        round1_methods=Slot((), True),
        coverage_floor=Slot(CoverageFloor(5, 3.0, 5.0), True),
    )
    research = replace(new_research("r-cn", NOW), brief=brief)
    payload = symbol_selection_payload(research)
    assert payload is not None
    assert payload["overrideNote"] == "已覆盖默认的池"
    assert "默认认" not in payload["summaryLine"]


def test_pool_shrink_disclosure_hidden_when_zero() -> None:
    from engine.research.pool_data_shrink import pool_shrink_disclosure

    assert pool_shrink_disclosure(0, 40) == ""
