from dataclasses import replace
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.models import ResearchAction
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from tests.test_loop_runtime import running_research


def test_running_view_omits_current_action_when_idle(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "idle.db")
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    idle_running = replace(running_research(), current_action=ResearchAction.IDLE)
    store.create(idle_running)
    view = service.view_for("#/research/r-loop")
    assert view["kind"] == "running"
    assert "currentAction" not in view
