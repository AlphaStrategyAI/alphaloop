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


def test_list_date_is_the_pool_calendar_day() -> None:
    import json
    from pathlib import Path

    payload = symbol_selection_payload(_research_with_pool())
    assert payload is not None
    pool_path = (
        Path(__file__).resolve().parents[1]
        / "engine"
        / "research"
        / "symbol_pools"
        / f"us_equity_large_cap_v{payload['listVersion']}.json"
    )
    generated = json.loads(pool_path.read_text(encoding="utf-8"))["generated_date"]
    assert payload["generatedDate"] == generated
    assert f"名单日 {generated}" in payload["summaryLine"]
    for field in ("dataStart", "dataEnd", "dataCutoff"):
        assert len(payload[field]) == 10 and payload[field][4] == "-" and "T" not in payload[field]
    assert payload["dataCutoff"] == payload["dataEnd"]


def test_symbol_selection_summary_line_once_lists_pool_name() -> None:
    payload = symbol_selection_payload(_research_with_pool())
    assert payload is not None
    line = format_symbol_selection_summary(payload)
    assert payload["summaryLine"] == line
    assert line == "美股大市值池 · 503 只 · 名单日 2026-10-16"
    assert line.count("美股大市值池") == 1
    assert "版本" not in line
    assert payload["listVersion"] == "2"
    assert payload["listNote"] == "取自标普 500 在名单日的成分，非时点成分"
    assert payload["listNameEn"] == "US large-cap universe · 503 names · list date 2026-10-16"
    assert payload["listNoteEn"] == (
        "Taken from S&P 500 membership on the list date; not point-in-time."
    )


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
    assert payload["summaryLine"] == "1 只 · 用户指定标的 · 已覆盖默认的池"
    assert "版本" not in payload["summaryLine"]


def test_pool_shrink_disclosure_hidden_when_zero() -> None:
    from engine.research.pool_data_shrink import pool_shrink_disclosure

    assert pool_shrink_disclosure(0, 40) == ""
