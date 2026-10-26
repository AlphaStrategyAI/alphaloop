"""#151 preselection: only a single licensed configured source is filled in."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.main import ResearchCommandService
from engine.research.models import Market, ResearchStatus, new_research
from engine.research.price_source_choice import (
    PriceSource,
    available_price_sources,
    preselect_price_source,
    save_configured_licensed_source,
)
from engine.research.runtime import EnginePaths
from engine.research.source_acknowledgement import record_acknowledgement
from engine.research.store import SQLiteStore
from tests.test_state_machine import NOW
from tests.test_view_data_source import _confirm_draft


def _licensed(source_id: str, market: Market = Market.US) -> PriceSource:
    return PriceSource(
        source_id=source_id,
        label=source_id,
        unlicensed=False,
        configured=True,
        market=market,
    )


def _yahoo() -> PriceSource:
    return PriceSource("yahoo_daily", "雅虎日线", True, True, Market.US)


def test_only_yahoo_is_not_preselected() -> None:
    assert preselect_price_source((_yahoo(),)) is None


def test_exactly_one_licensed_local_file_is_preselected() -> None:
    chosen = preselect_price_source((_licensed("local-file-desk"),))
    assert chosen == "local-file-desk"


def test_two_licensed_sources_are_not_preselected() -> None:
    sources = (_licensed("local-file-desk"), _licensed("local-file-backup"))
    assert preselect_price_source(sources) is None


def test_licensed_local_file_plus_yahoo_preselects_the_local_file() -> None:
    sources = (_licensed("local-file-desk"), _yahoo())
    assert preselect_price_source(sources) == "local-file-desk"


def test_acknowledgement_does_not_make_yahoo_eligible() -> None:
    acknowledged = PriceSource("yahoo_daily", "雅虎日线", True, True, Market.US)
    assert preselect_price_source((acknowledged,)) is None


def test_confirm_card_only_yahoo_shows_not_selected(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "a.db")
    store.create(_confirm_draft("r-us", Market.US, ("SPY",)))
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    selection = service.view_for("#/research/r-us")["symbolSelection"]
    assert selection["dataSource"] == "待选择"
    assert selection["dataSourcePending"] is True
    assert selection["dataSourceId"] in ("", None)
    yahoo = next(item for item in selection["priceSources"] if item["id"] == "yahoo_daily")
    assert yahoo["unlicensed"] is True
    assert store.load("r-us").data_source_id == ""


def test_confirm_card_preselects_one_configured_local_file(tmp_path: Path) -> None:
    paths = EnginePaths.for_colocated_root(tmp_path)
    save_configured_licensed_source(
        paths.data.settings_file,
        source_id="local-file-desk",
        label="Desk CSV",
        market=Market.US,
    )
    store = SQLiteStore(tmp_path / "b.db")
    store.create(_confirm_draft("r-us", Market.US, ("SPY",)))
    selection = ResearchCommandService(store, paths).view_for("#/research/r-us")["symbolSelection"]
    assert selection["dataSourcePending"] is False
    assert selection["dataSourceId"] == "local-file-desk"
    assert selection["dataSource"] == "Desk CSV"
    ids = [item["id"] for item in selection["priceSources"]]
    assert "local-file-desk" in ids
    assert "yahoo_daily" in ids
    assert store.load("r-us").data_source_id == ""


def test_confirm_card_two_licensed_sources_stay_not_selected(tmp_path: Path) -> None:
    paths = EnginePaths.for_colocated_root(tmp_path)
    for source_id, label in (
        ("local-file-desk", "Desk CSV"),
        ("local-file-backup", "Backup CSV"),
    ):
        save_configured_licensed_source(
            paths.data.settings_file,
            source_id=source_id,
            label=label,
            market=Market.US,
        )
    store = SQLiteStore(tmp_path / "c.db")
    store.create(_confirm_draft("r-us", Market.US, ("SPY",)))
    selection = ResearchCommandService(store, paths).view_for("#/research/r-us")["symbolSelection"]
    assert selection["dataSource"] == "待选择"
    assert selection["dataSourcePending"] is True
    assert selection["dataSourceId"] in ("", None)
    licensed = [item for item in selection["priceSources"] if not item["unlicensed"]]
    assert len(licensed) == 2


def test_confirm_card_local_file_and_yahoo_preselects_the_file(tmp_path: Path) -> None:
    paths = EnginePaths.for_colocated_root(tmp_path)
    save_configured_licensed_source(
        paths.data.settings_file,
        source_id="local-file-desk",
        label="Desk CSV",
        market=Market.US,
    )
    sources = available_price_sources(Market.US, paths.data.settings_file)
    assert preselect_price_source(sources) == "local-file-desk"
    store = SQLiteStore(tmp_path / "d.db")
    store.create(_confirm_draft("r-us", Market.US, ("SPY",)))
    selection = ResearchCommandService(store, paths).view_for("#/research/r-us")["symbolSelection"]
    assert selection["dataSourceId"] == "local-file-desk"
    assert selection["dataSourcePending"] is False
    yahoo = next(item for item in selection["priceSources"] if item["id"] == "yahoo_daily")
    assert yahoo["unlicensed"] is True


def test_new_research_stays_not_selected_after_yahoo_was_acknowledged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = EnginePaths.for_colocated_root(tmp_path)
    store = SQLiteStore(tmp_path / "e.db")
    store.create(_confirm_draft("r-ran", Market.US, ("SPY",)))
    service = ResearchCommandService(store, paths)
    monkeypatch.setattr("engine.main.ensure_runnable_universe", lambda item: item)
    record_acknowledgement("yahoo_daily", NOW, paths.data.settings_file)
    service.handle(
        {
            "type": "confirm_run",
            "research_id": "r-ran",
            "data_source_id": "yahoo_daily",
        }
    )
    assert store.load("r-ran").status is ResearchStatus.RUNNING
    assert store.load("r-ran").data_source_id == "yahoo_daily"

    fresh = new_research("r-next", NOW)
    store.create(_confirm_draft("r-next", Market.US, ("AAPL",)))
    assert fresh.data_source_id == ""
    selection = service.view_for("#/research/r-next")["symbolSelection"]
    assert selection["dataSource"] == "待选择"
    assert selection["dataSourcePending"] is True
    assert selection["dataSourceId"] in ("", None)
    assert store.load("r-next").data_source_id == ""
    yahoo = next(item for item in selection["priceSources"] if item["id"] == "yahoo_daily")
    assert yahoo["unlicensed"] is True
    assert yahoo["acknowledgedAt"] == NOW.isoformat()
    assert selection["dataSourceId"] != "yahoo_daily"

    record_acknowledgement("akshare_sina_daily", NOW, paths.data.settings_file)
    store.create(_confirm_draft("r-cn", Market.CN, ("600519.SH",)))
    cn = service.view_for("#/research/r-cn")["symbolSelection"]
    assert cn["dataSourcePending"] is True
    assert cn["dataSourceId"] in ("", None)
    akshare = next(item for item in cn["priceSources"] if item["id"] == "akshare_sina_daily")
    assert akshare["unlicensed"] is True
    assert akshare["acknowledgedAt"] == NOW.isoformat()
    assert cn["dataSourceId"] != "akshare_sina_daily"
    yahoo_again = service.view_for("#/research/r-next")["symbolSelection"]
    yahoo_row = next(item for item in yahoo_again["priceSources"] if item["id"] == "yahoo_daily")
    assert yahoo_row["acknowledgedAt"] == NOW.isoformat()
    assert all(item["id"] != "akshare_sina_daily" or item.get("acknowledgedAt") for item in yahoo_again["priceSources"])
