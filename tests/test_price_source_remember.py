"""Edit on the confirm card keeps the chosen source and its acknowledgement together."""

from __future__ import annotations

from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.runtime import EnginePaths
from engine.research.source_acknowledgement import acknowledged_at
from engine.research.store import SQLiteStore


def test_edit_keeps_yahoo_selection_and_acknowledgement(tmp_path: Path) -> None:
    service = ResearchCommandService(
        SQLiteStore(tmp_path / "remember.db"),
        EnginePaths.for_colocated_root(tmp_path),
    )
    research_id = service.handle({"type": "create_draft"})["research_id"]
    for message in (
        "Mean reversion on AAPL, a US stock, using daily prices.",
        "30 minutes",
        "subperiod robustness check, out-of-sample stability, concentration, turnover cost",
        "at least 1 name, 10 years of history, and no more than 5% missing.",
    ):
        service.handle({"type": "send_dialogue", "research_id": research_id, "message": message})
    assert service.view_for(f"#/research/{research_id}")["kind"] == "confirm_run"

    service.handle(
        {
            "type": "set_price_source",
            "research_id": research_id,
            "data_source_id": "yahoo_daily",
            "unlicensed_acknowledged": True,
        }
    )
    chosen = service.view_for(f"#/research/{research_id}")["symbolSelection"]
    assert chosen["dataSourceId"] == "yahoo_daily"
    assert chosen["dataSourcePending"] is False
    assert chosen["dataSource"] != "待选择"
    yahoo = next(item for item in chosen["priceSources"] if item["id"] == "yahoo_daily")
    assert yahoo["acknowledgedAt"]
    assert (
        acknowledged_at("yahoo_daily", service.paths.data.settings_file) == yahoo["acknowledgedAt"]
    )

    service.handle({"type": "unlock_brief", "research_id": research_id, "slot": "coverage_floor"})
    draft = service.view_for(f"#/research/{research_id}")
    assert draft["kind"] == "draft"
    assert service.store.load(research_id).data_source_id == "yahoo_daily"

    service.handle(
        {
            "type": "send_dialogue",
            "research_id": research_id,
            "message": "at least 25 names, 10 years of history, and no more than 5% missing.",
        }
    )
    back = service.view_for(f"#/research/{research_id}")
    assert back["kind"] == "confirm_run"
    selection = back["symbolSelection"]
    assert selection["dataSourceId"] == "yahoo_daily"
    assert selection["dataSourcePending"] is False
    assert selection["dataSource"] != "待选择"
    yahoo_again = next(item for item in selection["priceSources"] if item["id"] == "yahoo_daily")
    assert yahoo_again["acknowledgedAt"] == yahoo["acknowledgedAt"]
    assert back["runGate"]["code"] == "UNIVERSE_TOO_FEW_SYMBOLS"
    assert back["runGate"]["runnable"] is False


def test_clearing_the_source_does_not_erase_the_acknowledgement(tmp_path: Path) -> None:
    service = ResearchCommandService(
        SQLiteStore(tmp_path / "clear.db"),
        EnginePaths.for_colocated_root(tmp_path),
    )
    research_id = service.handle({"type": "create_draft"})["research_id"]
    for message in (
        "Mean reversion on AAPL, a US stock, using daily prices.",
        "12 hours",
        "turnover cost",
        "at least 1 name, 10 years of history, and no more than 5% missing.",
    ):
        service.handle({"type": "send_dialogue", "research_id": research_id, "message": message})
    service.handle(
        {
            "type": "set_price_source",
            "research_id": research_id,
            "data_source_id": "yahoo_daily",
            "unlicensed_acknowledged": True,
        }
    )
    stamped = acknowledged_at("yahoo_daily", service.paths.data.settings_file)
    assert stamped
    service.handle(
        {
            "type": "set_price_source",
            "research_id": research_id,
            "data_source_id": "",
        }
    )
    view = service.view_for(f"#/research/{research_id}")["symbolSelection"]
    assert view["dataSourcePending"] is True
    assert view["dataSourceId"] in ("", None)
    assert view["dataSource"] == "待选择"
    yahoo = next(item for item in view["priceSources"] if item["id"] == "yahoo_daily")
    assert yahoo["acknowledgedAt"] == stamped
    assert service.store.load(research_id).data_source_id == ""
