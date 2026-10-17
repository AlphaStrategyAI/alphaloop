from datetime import UTC, datetime
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.models import DialogueRole, new_research
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def _service(tmp_path: Path) -> ResearchCommandService:
    store = SQLiteStore(tmp_path / "d.db")
    paths = EnginePaths.for_colocated_root(tmp_path)
    return ResearchCommandService(store, paths)


def test_send_dialogue_off_topic_persists_user_and_reply(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "d.db")
    research = new_research("r-draft", NOW)
    store.create(research)
    service = _service(tmp_path)

    service.handle({"type": "send_dialogue", "research_id": "r-draft", "message": "你好"})

    loaded = store.load("r-draft")
    assert len(loaded.dialogue) == 2
    assert loaded.dialogue[0].role is DialogueRole.USER
    assert loaded.dialogue[0].text == "你好"
    assert loaded.dialogue[1].role is DialogueRole.ASSISTANT
    assert "原理想靠什么赚钱" in loaded.dialogue[1].text

    view = service.view_for("#/research/r-draft")
    assert view["kind"] == "draft"
    assert len(view["dialogue"]) == 2
    assert view["dialogue"][1]["text"] == loaded.dialogue[1].text


def test_send_dialogue_on_topic_returns_next_question(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "d.db")
    store.create(new_research("r-draft", NOW))
    service = _service(tmp_path)

    service.handle(
        {
            "type": "send_dialogue",
            "research_id": "r-draft",
            "message": "最长研究时间 12 小时",
        }
    )

    loaded = store.load("r-draft")
    assert loaded.brief.max_effective_hours.value == 12.0
    assert loaded.dialogue[-1].role is DialogueRole.ASSISTANT
    assert "原理想靠什么赚钱" in loaded.dialogue[-1].text


def test_dialogue_round_trip_sqlite_reload(tmp_path: Path) -> None:
    path = tmp_path / "persist.db"
    store = SQLiteStore(path)
    store.create(new_research("r-draft", NOW))
    paths = EnginePaths.for_colocated_root(tmp_path)
    service = ResearchCommandService(store, paths)
    service.handle({"type": "send_dialogue", "research_id": "r-draft", "message": "你好"})

    reloaded = SQLiteStore(path)
    research = reloaded.load("r-draft")
    assert len(research.dialogue) == 2


def test_unlock_brief_schema_and_handler(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "d.db")
    research = new_research("r-draft", NOW)
    store.create(research)
    service = _service(tmp_path)
    service.handle({"type": "unlock_brief", "research_id": "r-draft"})
    loaded = store.load("r-draft")
    assert all(not getattr(loaded.brief, name).locked for name in (
        "thesis", "universe", "max_effective_hours", "round1_methods", "coverage_floor"
    ))


def test_unlock_brief_single_slot(tmp_path: Path) -> None:
    from dataclasses import replace

    from tests.test_state_machine import locked_brief

    research = replace(new_research("r-draft", NOW), brief=locked_brief())
    service = _service(tmp_path)
    service.store.create(research)
    service.handle(
        {"type": "unlock_brief", "research_id": "r-draft", "slot": "universe"}
    )
    loaded = service.store.load("r-draft")
    assert not loaded.brief.universe.locked
    assert loaded.brief.thesis.locked
