from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.models import ResearchEvent, ResearchStatus, new_research
from engine.research.runtime import EnginePaths
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from tests.test_state_machine import locked_brief

NOW = datetime(2026, 10, 17, 8, 0, tzinfo=UTC)


def test_confirm_modification_replaces_pending_reply_with_started_version(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "modc.db")
    brief = locked_brief()
    paused = transition(
        replace(new_research("r-modc", NOW), brief=brief, status=ResearchStatus.DRAFT),
        ResearchEvent.CONFIRM_RUN,
        NOW,
    )
    paused = transition(paused, ResearchEvent.PAUSE, NOW)
    store.create(paused)
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    service.handle(
        {
            "type": "send_dialogue",
            "research_id": "r-modc",
            "message": "把最长研究时间改成 6 小时",
        }
    )
    service.handle({"type": "confirm_modification", "research_id": "r-modc"})
    loaded = store.load("r-modc")
    assert loaded.dialogue[-1].text.startswith("已开始第")
    assert "确认修改并开新版" not in loaded.dialogue[-1].text
