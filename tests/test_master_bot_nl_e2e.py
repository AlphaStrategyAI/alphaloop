"""Master Bot natural-language repro: empty DB → confirm with pool → run one round."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.main import ResearchCommandService
from engine.research.clock import TimeBudget
from engine.research.loop import ResearchLoop
from engine.research.models import ResearchStatus
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError
from tests.test_loop_runtime import FakeBuilder, FakeMonotonic, NOW, PassReviewer

THESIS = "美股股票的均值回归"
ANSWERS = (
    "4 小时",
    "走样检验、样本外稳定",
    "至少 20 个标的",
    "10 年",
    "缺失不超过 5%",
)


def _service(tmp_path: Path) -> ResearchCommandService:
    return ResearchCommandService(
        SQLiteStore(tmp_path / "master.db"),
        EnginePaths.for_colocated_root(tmp_path),
    )


def _dialogue_to_confirm(service: ResearchCommandService, research_id: str) -> dict:
    service.handle({"type": "send_dialogue", "research_id": research_id, "message": THESIS})
    for message in ANSWERS:
        service.handle({"type": "send_dialogue", "research_id": research_id, "message": message})
    view = service.view_for(f"#/research/{research_id}")
    assert view["kind"] == "confirm_run"
    sel = view["symbolSelection"]
    assert sel is not None
    assert sel["listName"] == "美股大市值池 · 503 只 · 名单日 2026-10-16"
    assert sel["listVersion"] == "2"
    assert sel["summaryLine"] == "美股大市值池 · 503 只 · 名单日 2026-10-16"
    assert "版本" not in sel["summaryLine"]
    assert sel["listNote"] == "取自标普 500 在名单日的成分，非时点成分"
    assert sel["count"] == 503
    assert len(sel["symbols"]) == 503
    assert sel["isDefaultPool"] is True
    assert sel["dataStart"]
    assert sel["dataEnd"]
    assert view.get("chatEnabled") is False
    assert view["dialogue"]
    return view


def test_master_bot_nl_split_coverage_reaches_confirm_with_pool(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = service.handle({"type": "create_draft"})["research_id"]
    _dialogue_to_confirm(service, research_id)


def test_master_bot_nl_confirm_starts_and_runs_one_round(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = service.handle({"type": "create_draft"})["research_id"]
    _dialogue_to_confirm(service, research_id)
    service.handle({"type": "confirm_run", "research_id": research_id, "data_source_id": "yahoo_daily", "unlicensed_acknowledged": True})
    loaded = service.store.load(research_id)
    assert loaded.status is ResearchStatus.RUNNING
    assert len(loaded.brief.universe.value.symbols) == 503
    loop = ResearchLoop(
        service.store,
        FakeBuilder(),
        PassReviewer(),
        TimeBudget(FakeMonotonic()),
        lambda: datetime.now(UTC),
    )
    loop.run_once(research_id)
    after = service.store.load(research_id)
    assert len(after.versions[0].rounds) >= 1


def test_missing_pool_returns_question_in_chat_and_enables_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import engine.research.symbol_pool as symbol_pool

    monkeypatch.setattr(symbol_pool, "list_pool_files", lambda: ())
    service = _service(tmp_path)
    research_id = service.handle({"type": "create_draft"})["research_id"]
    for message in (THESIS, *ANSWERS):
        service.handle({"type": "send_dialogue", "research_id": research_id, "message": message})
    view = service.view_for(f"#/research/{research_id}")
    assert view["kind"] == "draft"
    assert view.get("chatEnabled") is True
    with pytest.raises(UserFacingError):
        service.handle({"type": "confirm_run", "research_id": research_id, "data_source_id": "yahoo_daily", "unlicensed_acknowledged": True})
    view = service.view_for(f"#/research/{research_id}")
    assert view["kind"] == "draft"
    assert any("要用哪组标的" in turn["text"] for turn in view["dialogue"])
    assert view.get("chatEnabled") is True
