from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.models import (
    AssetClass,
    Market,
    ResearchStatus,
    Slot,
    Universe,
    new_research,
)
from engine.research.market_data_progress import (
    clear_market_data_progress,
    set_market_data_progress,
)
from engine.research.progress import (
    host_status,
    host_status_while_fetching,
    list_items,
    notification_event,
    thesis_divergence_hint,
)
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def test_host_status_priority_is_awaiting_then_running_then_completed_then_idle() -> None:
    idle = new_research("r-idle", NOW)
    running = replace(new_research("r-run", NOW), status=ResearchStatus.RUNNING)
    awaiting = replace(new_research("r-wait", NOW), status=ResearchStatus.AWAITING_CONFIRM)
    done = replace(new_research("r-done", NOW), status=ResearchStatus.COMPLETED)
    assert host_status(()) == "idle"
    assert host_status((idle, done)) == "completed"
    assert host_status((idle, done, running)) == "running"
    assert host_status((idle, done, running, awaiting)) == "awaiting_confirm"


def test_live_quote_fetch_is_running_even_when_another_study_is_waiting(tmp_path: Path) -> None:
    assert host_status_while_fetching("awaiting_confirm", fetching=True) == "running"
    assert host_status_while_fetching("completed", fetching=True) == "running"
    assert host_status_while_fetching("awaiting_confirm", fetching=False) == "awaiting_confirm"
    store = SQLiteStore(tmp_path / "host.db")
    store.create(replace(new_research("r-wait", NOW), status=ResearchStatus.AWAITING_CONFIRM))
    store.create(new_research("r-us", NOW))
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    set_market_data_progress(12, 503, "yahoo")
    try:
        progress = service.handle({"type": "market_data_progress"})
        view = service.view_for("#/research/r-us")
    finally:
        clear_market_data_progress()
    assert progress["hostStatus"] == "running"
    assert progress["marketDataProgress"] == {"done": 12, "total": 503, "source": "yahoo"}
    assert view["hostStatus"] == "running"


def test_list_items_include_universe_timestamps_and_status_filter() -> None:
    research = replace(
        new_research("r-1", NOW),
        brief=replace(
            new_research("r-1", NOW).brief,
            thesis=Slot("美股低波动回归", True),
            universe=Slot(
                Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAPL",)),
                True,
            ),
        ),
        status=ResearchStatus.DRAFT,
    )
    rows = list_items((research,), None)
    assert rows[0].title == "美股低波动回归"
    assert rows[0].universe_label == "美股 · 股票"
    assert rows[0].created_at == NOW
    assert list_items((research,), ResearchStatus.RUNNING) == ()
    assert list_items((research,), ResearchStatus.DRAFT)[0].research_id == "r-1"


def test_missing_thesis_list_title_is_empty() -> None:
    research = new_research("r-empty", NOW)
    assert list_items((research,), None)[0].title == ""


def test_thesis_hint_is_non_blocking() -> None:
    hint = thesis_divergence_hint("低波动量价回归", "用宏观利率做国债久期")
    assert hint == "这也可以作为一条新研究重新开始。"
    assert thesis_divergence_hint("低波动量价回归", "低波动量价回归加拥挤过滤") is None


def test_notifications_fire_only_for_awaiting_and_terminal_states() -> None:
    assert notification_event(ResearchStatus.RUNNING, ResearchStatus.AWAITING_CONFIRM) == "awaiting_confirm"
    assert notification_event(ResearchStatus.RUNNING, ResearchStatus.COMPLETED) == "completed"
    assert notification_event(ResearchStatus.RUNNING, ResearchStatus.ENDED) == "ended"
    assert notification_event(ResearchStatus.DRAFT, ResearchStatus.RUNNING) is None
    assert notification_event(ResearchStatus.RUNNING, ResearchStatus.PAUSED) is None
    assert notification_event(ResearchStatus.AWAITING_CONFIRM, ResearchStatus.RUNNING) is None


def test_fetch_view_drains_every_pending_notification(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    service = ResearchCommandService(
        store,
        EnginePaths.for_colocated_root(tmp_path),
    )
    first = replace(new_research("r-wait", NOW), status=ResearchStatus.RUNNING)
    second = replace(new_research("r-done", NOW), status=ResearchStatus.RUNNING)
    store.create(first)
    store.create(second)
    primed = service.view_for("#/research")
    assert "notify" not in primed

    later = datetime(2026, 8, 28, 13, 0, tzinfo=UTC)
    store.save(replace(first, status=ResearchStatus.AWAITING_CONFIRM, updated_at=later), NOW)
    store.save(replace(second, status=ResearchStatus.COMPLETED, updated_at=later), NOW)

    drained = service.view_for("#/research")
    assert drained["notify"] == "awaiting_confirm"
    assert drained["notifies"] == ["awaiting_confirm", "completed"]

    quiet = service.view_for("#/research")
    assert "notify" not in quiet
    assert "notifies" not in quiet
