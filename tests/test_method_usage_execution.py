"""Method library usage counts executions, not just brief selection."""

from pathlib import Path

import pytest

from engine.main import ResearchCommandService
from engine.research.loop import ResearchLoop
from engine.research.methods import distinct_research_usage_count
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from tests.test_loop_runtime import (
    NOW,
    FailedMethodsParamBuilder,
    PassReviewer,
    TimeBudget,
    running_research,
)


def test_verification_execution_increments_usage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "1")
    store = SQLiteStore(tmp_path / "usage.db")
    store.create(running_research())
    ResearchLoop(
        store,
        FailedMethodsParamBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert distinct_research_usage_count(store, "scorecard.market") >= 1
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    methods = service.view_for("#/methods")["methods"]
    scorecard = next(item for item in methods if item["id"] == "scorecard.market")
    assert scorecard["usageCount"] >= 1
