from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.main import ResearchCommandService
from engine.research.clock import TimeBudget
from engine.research.loop import ResearchLoop
from engine.research.models import ResearchStatus
from engine.research.runtime import RuntimePaths
from engine.research.store import SQLiteStore
from tests.test_cumulative_trials import FailTwiceThenPassBuilder
from tests.test_loop_runtime import NOW, PassReviewer, running_research


def test_continue_iterate_returns_without_inline_run_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "1")
    store = SQLiteStore(tmp_path / "ci.db")
    paths = RuntimePaths(tmp_path, tmp_path / "lock", tmp_path / "owner.json")
    service = ResearchCommandService(store, paths)
    store.create(running_research())
    loop = ResearchLoop(
        store,
        FailTwiceThenPassBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    )
    completed = loop.run_once("r-loop")
    assert completed.status is ResearchStatus.COMPLETED

    def fail_run(_store, _paths):
        raise AssertionError("continue_iterate must not invoke build_loop().run_once inline")

    monkeypatch.setattr("engine.main.build_loop", fail_run)

    payload = service.handle(
        {
            "type": "continue_iterate",
            "research_id": "r-loop",
            "user_confirmed": True,
        }
    )
    assert payload["status"] == "running"
    loaded = store.load("r-loop")
    assert loaded.status is ResearchStatus.RUNNING
