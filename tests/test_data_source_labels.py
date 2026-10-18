from dataclasses import replace
from datetime import UTC, datetime

from engine.research.confirm_view import symbol_selection_payload
from engine.research.display_names import data_source_label
from engine.research.models import (
    AssetClass,
    CoverageFloor,
    Market,
    ResearchBrief,
    Slot,
    Universe,
    new_research,
)
from engine.research.planned_data_window import (
    AKSHARE_SINA_DATA_SOURCE_ID,
    data_source_id_for_market,
)

NOW = datetime(2026, 10, 18, 3, 0, tzinfo=UTC)


def test_data_source_labels_by_market() -> None:
    assert data_source_label("yahoo_daily") == "雅虎日线"
    assert data_source_label("akshare_sina_daily") == "AkShare 日线（新浪优先）"
    assert data_source_id_for_market(Market.CN) == AKSHARE_SINA_DATA_SOURCE_ID
    assert data_source_id_for_market(Market.US) == "yahoo_daily"


def test_cn_confirm_card_data_source() -> None:
    brief = ResearchBrief(
        thesis=Slot("A股回归", True),
        universe=Slot(
            Universe(
                Market.CN,
                AssetClass.EQUITY,
                AssetClass.EQUITY,
                ("600519.SH",),
                user_symbols_override=True,
            ),
            True,
        ),
        max_effective_hours=Slot(3.0, True),
        round1_methods=Slot((), True),
        coverage_floor=Slot(CoverageFloor(5, 3.0, 5.0), True),
    )
    research = replace(
        new_research("r-cn", NOW),
        brief=brief,
        data_source_id=AKSHARE_SINA_DATA_SOURCE_ID,
    )
    payload = symbol_selection_payload(research)
    assert payload is not None
    assert payload["dataSource"] == "AkShare 日线（新浪优先）"
    assert "雅虎" not in payload["dataSource"]
