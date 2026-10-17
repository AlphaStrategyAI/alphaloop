from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.dialogue.modification import brief_differs_from_latest_version
from engine.main import ResearchCommandService
from engine.research.models import ResearchStatus, new_research
from engine.research.runtime import EnginePaths
from engine.research.state_machine import transition
from engine.research.models import ResearchEvent
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError
from tests.test_state_machine import locked_brief

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def test_modification_dialogue_updates_hours_on_paused_research(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "mod.db")
    research = replace(
        new_research("r-mod", NOW),
        brief=locked_brief(),
        status=ResearchStatus.PAUSED,
        versions=(),
    )
    store.create(research)
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    service.handle(
        {
            "type": "send_dialogue",
            "research_id": "r-mod",
            "message": "把最长研究时间改成 6 小时",
        }
    )
    loaded = store.load("r-mod")
    assert loaded.brief.max_effective_hours.value == 6.0
    assert loaded.dialogue[-1].role.value == "assistant"


def test_confirm_modification_rejects_unchanged_brief(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "unchanged.db")
    brief = locked_brief()
    research = replace(new_research("r-same", NOW), brief=brief, status=ResearchStatus.DRAFT)
    research = transition(research, ResearchEvent.CONFIRM_RUN, NOW)
    research = transition(research, ResearchEvent.PAUSE, NOW)
    store.create(research)
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    with pytest.raises(UserFacingError) as exc:
        service.handle({"type": "confirm_modification", "research_id": "r-same"})
    assert exc.value.code == "MODIFICATION_UNCHANGED"
