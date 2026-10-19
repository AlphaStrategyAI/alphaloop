"""Chat draft → confirm → run without hand-seeded briefs."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.main import ResearchCommandService
from engine.research.clock import TimeBudget
from engine.research.data_errors import EmptySymbolsError
from engine.research.data_window import data_window_key_from_research
from engine.research.gather import AkShareDataAdapter, RoutingDataAdapter, YahooDataAdapter
from engine.research.loop import ResearchLoop
from engine.research.models import ResearchStatus
from engine.research.run_errors import apply_run_failure
from engine.research.runtime import EnginePaths
from engine.research.user_errors import classify_run_error
from tests.test_loop_runtime import FakeBuilder, FakeMonotonic, NOW, PassReviewer

DIALOGUE_SEQUENCE = (
    "美股股票的均值回归",
    "12 小时",
    "走样检验 样本外稳定 拥挤度 换手成本",
    "至少 25 个 10 年 缺失不超过 5%",
)


def _service(tmp_path: Path) -> ResearchCommandService:
    store = SQLiteStore(tmp_path / "e2e.db")
    paths = EnginePaths.for_colocated_root(tmp_path)
    return ResearchCommandService(store, paths)


from engine.research.store import SQLiteStore


def _dialogue_to_confirm(service: ResearchCommandService, research_id: str) -> dict:
    for message in DIALOGUE_SEQUENCE:
        service.handle(
            {"type": "send_dialogue", "research_id": research_id, "message": message}
        )
    view = service.view_for(f"#/research/{research_id}")
    assert view["kind"] == "confirm_run"
    sel = view.get("symbolSelection")
    assert sel is not None
    assert sel["count"] >= 100
    assert sel["listVersion"] == "2"
    assert sel["summaryLine"] == "503 只 · 美股大市值 · 版本 2 · 2026-10-16 · 默认标的池"
    assert sel["dataCutoff"]
    return view


def test_single_message_thesis_advances_dialogue(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = service.handle({"type": "create_draft"})["research_id"]
    service.handle(
        {"type": "send_dialogue", "research_id": research_id, "message": "美股股票的均值回归"}
    )
    loaded = service.store.load(research_id)
    assert loaded.brief.thesis.value is not None
    assert loaded.brief.universe.value is not None
    view = service.view_for(f"#/research/{research_id}")
    assert view["kind"] == "draft"


def test_chat_draft_confirm_run_populates_symbols_and_runs_one_round(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    research_id = service.handle({"type": "create_draft"})["research_id"]
    _dialogue_to_confirm(service, research_id)

    service.handle({"type": "confirm_run", "research_id": research_id})
    loaded = service.store.load(research_id)
    assert loaded.status is ResearchStatus.RUNNING
    symbols = loaded.brief.universe.value.symbols
    assert len(symbols) >= 100
    assert loaded.symbol_list_version == "us_equity_large_cap_v2"
    assert "prices must be non-empty" not in (loaded.last_run_error or "")

    mono = FakeMonotonic()
    loop = ResearchLoop(
        service.store,
        FakeBuilder(),
        PassReviewer(),
        TimeBudget(mono),
        lambda: datetime.now(UTC),
    )
    loop.run_once(research_id)
    after = service.store.load(research_id)
    assert len(after.versions[0].rounds) >= 1


def test_second_research_inherits_window_cumulative(tmp_path: Path) -> None:
    service = _service(tmp_path)
    rid_a = service.handle({"type": "create_draft"})["research_id"]
    _dialogue_to_confirm(service, rid_a)
    service.handle({"type": "confirm_run", "research_id": rid_a})
    mono = FakeMonotonic()
    loop = ResearchLoop(
        service.store,
        FakeBuilder(),
        PassReviewer(),
        TimeBudget(mono),
        lambda: datetime.now(UTC),
    )
    loop.run_once(rid_a)
    research_a = service.store.load(rid_a)
    key = data_window_key_from_research(research_a)
    assert key is not None
    assert service.store.window_round_count(key.serialize()) >= 1

    rid_b = service.handle({"type": "create_draft"})["research_id"]
    _dialogue_to_confirm(service, rid_b)
    service.handle({"type": "confirm_run", "research_id": rid_b})
    view_b = service.view_for(f"#/research/{rid_b}")
    assert view_b.get("windowCumulativeRoundsAllResearches", 0) >= 1


def test_empty_symbols_classified_for_ui(tmp_path: Path) -> None:
    code, message = classify_run_error(EmptySymbolsError())
    assert code == "DATA_SYMBOLS_EMPTY"
    assert "标的" in message


def test_routing_adapter_empty_symbols_never_returns_silent_empty_frame() -> None:
    adapter = RoutingDataAdapter(YahooDataAdapter(), AkShareDataAdapter())
    with pytest.raises(EmptySymbolsError):
        adapter.load_daily((), NOW.date(), NOW.date())
