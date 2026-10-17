"""Chat draft → confirm → run without hand-seeded briefs."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.main import ResearchCommandService, build_loop
from engine.research.clock import TimeBudget
from engine.research.data_errors import EmptySymbolsError
from engine.research.gather import RoutingDataAdapter
from engine.research.loop import ResearchLoop
from engine.research.models import ResearchStatus
from engine.research.run_errors import apply_run_failure
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.user_errors import classify_run_error
from tests.test_loop_runtime import FakeBuilder, FakeMonotonic, NOW, PassReviewer

DIALOGUE_LOCK_SEQUENCE = (
    "美股股票低波动回归策略 锁定资产类别并锁定大致原理",
    "走样检验 样本外稳定 拥挤度 换手成本 锁定第一轮",
    "12 小时 锁定最长研究时间",
    "至少 8 个 10 年 缺失不超过 5% 锁定最低覆盖",
)


def _service(tmp_path: Path) -> ResearchCommandService:
    store = SQLiteStore(tmp_path / "e2e.db")
    paths = EnginePaths.for_colocated_root(tmp_path)
    return ResearchCommandService(store, paths)


def _dialogue_to_confirm(service: ResearchCommandService, research_id: str) -> None:
    for message in DIALOGUE_LOCK_SEQUENCE:
        service.handle(
            {"type": "send_dialogue", "research_id": research_id, "message": message}
        )
    view = service.view_for(f"#/research/{research_id}")
    assert view["kind"] == "confirm_run"
    symbols_line = view["settings"].get("universe_symbols", "")
    assert symbols_line
    assert "SPY" in symbols_line


def test_chat_draft_confirm_run_populates_symbols_and_runs_one_round(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    research_id = service.handle({"type": "create_draft"})["research_id"]
    _dialogue_to_confirm(service, research_id)

    service.handle({"type": "confirm_run", "research_id": research_id})
    loaded = service.store.load(research_id)
    assert loaded.status is ResearchStatus.RUNNING
    symbols = loaded.brief.universe.value.symbols
    assert symbols
    assert "SPY" in symbols
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
    assert after.last_run_error is None or "prices must be non-empty" not in after.last_run_error


def test_empty_symbols_classified_for_ui(tmp_path: Path) -> None:
    code, message = classify_run_error(EmptySymbolsError())
    assert code == "DATA_SYMBOLS_EMPTY"
    assert "标的" in message

    research = _service(tmp_path).store.load(
        _service(tmp_path).handle({"type": "create_draft"})["research_id"]
    )
    research = replace(research, status=ResearchStatus.RUNNING)
    failed = apply_run_failure(research, message, NOW, code=code)
    assert failed.last_run_error_code == "DATA_SYMBOLS_EMPTY"
    assert "prices must be non-empty" not in (failed.last_run_error or "")


def test_routing_adapter_empty_symbols_never_returns_silent_empty_frame() -> None:
    from engine.research.gather import AkShareDataAdapter, YahooDataAdapter

    adapter = RoutingDataAdapter(YahooDataAdapter(), AkShareDataAdapter())
    with pytest.raises(EmptySymbolsError):
        adapter.load_daily((), NOW.date(), NOW.date())
