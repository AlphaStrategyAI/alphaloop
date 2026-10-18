from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.models import AssetClass, Market, ResearchStatus, Slot, Universe, new_research
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
