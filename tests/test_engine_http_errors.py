from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.main import ResearchCommandService
from engine.research.models import ResearchStatus, new_research
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError
from tests.test_state_machine import locked_brief

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _service(tmp_path: Path) -> ResearchCommandService:
    store = SQLiteStore(tmp_path / "http.db")
    paths = EnginePaths.for_colocated_root(tmp_path)
    return ResearchCommandService(store, paths)


def test_confirm_modification_while_running_raises_user_facing_error(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    research = replace(
        new_research("r-run", NOW),
        brief=locked_brief(),
        status=ResearchStatus.RUNNING,
    )
    service.store.create(research)
    with pytest.raises(UserFacingError) as exc:
        service.handle({"type": "confirm_modification", "research_id": "r-run"})
    assert exc.value.code == "RUNNING_CANNOT_MODIFY"


def test_unlock_brief_single_slot_keeps_other_locks(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research = replace(new_research("r-draft", NOW), brief=locked_brief())
    service.store.create(research)
    service.handle(
        {"type": "unlock_brief", "research_id": "r-draft", "slot": "max_effective_hours"}
    )
    loaded = service.store.load("r-draft")
    assert not loaded.brief.max_effective_hours.locked
    assert loaded.brief.thesis.locked
    assert loaded.brief.universe.locked
