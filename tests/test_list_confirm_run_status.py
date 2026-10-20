from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.models import (
    AssetClass,
    ConfirmKind,
    ConfirmRequest,
    Market,
    ResearchStatus,
    Slot,
    Universe,
    new_research,
)
from engine.export import strategy_pack_eligibility
from engine.research.progress import list_row_status
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.symbol_pool import pool_for_market
from tests.test_state_machine import locked_brief

NOW = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)


def test_list_row_status_confirm_ready_draft() -> None:
    pool = pool_for_market(Market.US, AssetClass.EQUITY, AssetClass.EQUITY)
    assert pool is not None
    brief = locked_brief()
    universe = Universe(
        Market.US,
        AssetClass.EQUITY,
        AssetClass.EQUITY,
        pool.symbols,
        symbol_list_version=pool.version_id,
        user_symbols_override=False,
    )
    brief = replace(brief, universe=Slot(universe, True))
    research = replace(new_research("r-list", NOW), brief=brief, status=ResearchStatus.DRAFT)
    assert list_row_status(research) == "confirm_run"


def test_list_row_status_gate_failed_completed_lists_as_ended() -> None:
    research = replace(new_research("r-fail", NOW), status=ResearchStatus.COMPLETED)
    assert not strategy_pack_eligibility(research).eligible
    assert list_row_status(research) == "ended"


def test_fetch_view_list_uses_confirm_run_status(tmp_path: Path) -> None:
    pool = pool_for_market(Market.US, AssetClass.EQUITY, AssetClass.EQUITY)
    assert pool is not None
    brief = locked_brief()
    universe = Universe(
        Market.US,
        AssetClass.EQUITY,
        AssetClass.EQUITY,
        pool.symbols,
        symbol_list_version=pool.version_id,
        user_symbols_override=False,
    )
    brief = replace(brief, universe=Slot(universe, True))
    research = replace(new_research("r-list", NOW), brief=brief, status=ResearchStatus.DRAFT)
    store = SQLiteStore(tmp_path / "list.db")
    store.create(research)
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    view = service.view_for("#/research")
    assert view["rows"][0]["status"] == "confirm_run"


def test_every_confirm_run_stays_on_the_list_and_opens_by_its_id(tmp_path: Path) -> None:
    earlier = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    later = datetime(2026, 10, 17, 15, 0, tzinfo=UTC)
    store = SQLiteStore(tmp_path / "list.db")
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    for research_id, thesis, when in (
        ("r-old", "older thesis", earlier),
        ("r-new", "newer thesis", later),
    ):
        brief = replace(locked_brief(), thesis=Slot(thesis, True))
        store.create(
            replace(new_research(research_id, when), brief=brief, updated_at=when)
        )
    view = service.view_for("#/research")
    confirm_rows = [row for row in view["rows"] if row["status"] == "confirm_run"]
    assert [row["id"] for row in confirm_rows] == ["r-new", "r-old"]
    for row in confirm_rows:
        opened = service.view_for(f"#/research/{row['id']}")
        assert opened["kind"] == "confirm_run"
        assert opened["researchId"] == row["id"]
        assert opened["settings"]["thesis"] == row["title"]


def test_every_awaiting_confirm_stays_addressable_and_opens_by_its_id(tmp_path: Path) -> None:
    earlier = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    later = datetime(2026, 10, 17, 15, 0, tzinfo=UTC)
    store = SQLiteStore(tmp_path / "list.db")
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    for research_id, proposed, when in (
        ("r-old", "older change", earlier),
        ("r-new", "newer change", later),
    ):
        pending = ConfirmRequest(
            request_id=f"req-{research_id}",
            kind=ConfirmKind.ECONOMIC,
            proposed_change=proposed,
            reason="reason",
            effect="effect",
            created_at=when,
        )
        store.create(
            replace(
                new_research(research_id, when),
                status=ResearchStatus.AWAITING_CONFIRM,
                pending_confirm=pending,
                current_version_number=1,
                updated_at=when,
            )
        )
    view = service.view_for("#/research")
    ids: list[str] = []
    if view["awaiting"] is not None:
        ids.append(view["awaiting"]["id"])
    ids.extend(
        row["id"] for row in view["rows"] if row["status"] == "awaiting_confirm"
    )
    assert ids == ["r-new", "r-old"]
    for research_id, proposed in (("r-new", "newer change"), ("r-old", "older change")):
        opened = service.view_for(f"#/research/{research_id}")
        assert opened["kind"] == "awaiting_confirm"
        assert opened["researchId"] == research_id
        assert opened["proposed"] == proposed
