import os
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.clock import TimeBudget
from engine.research.loop import ResearchLoop
from engine.research.models import ResearchStatus
from engine.research.runtime import RuntimePaths
from engine.research.store import SQLiteStore
from tests.test_export_pack import completed_research
from tests.test_loop_runtime import NOW, FailedMethodsParamBuilder, PassReviewer, running_research


def _visible_copy_chunks(view: dict) -> str:
    parts = [
        view.get("resultHeadline") or "",
        view.get("subtitle") or "",
        view.get("honestStopHint") or "",
    ]
    return "\n".join(str(p) for p in parts if p)


def test_exhausted_completed_view_shows_budget_copy_once(tmp_path: Path) -> None:
    os.environ["ALPHALOOP_MAX_TRIALS"] = "1"
    store = SQLiteStore(tmp_path / "dup.db")
    paths = RuntimePaths(tmp_path, tmp_path / "lock", tmp_path / "owner.json")
    service = ResearchCommandService(store, paths)
    store.create(running_research())
    completed = ResearchLoop(
        store,
        FailedMethodsParamBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert completed.status is ResearchStatus.COMPLETED
    view = service.view_for("#/research/r-loop")
    blob = _visible_copy_chunks(view)
    assert blob.count("预算已用尽") == 1
    assert not view.get("honestStopHint")


def test_ended_status_completed_view_shows_budget_copy_once(tmp_path: Path) -> None:
    from dataclasses import replace

    store = SQLiteStore(tmp_path / "ended.db")
    paths = RuntimePaths(tmp_path, tmp_path / "lock", tmp_path / "owner.json")
    service = ResearchCommandService(store, paths)
    base = replace(completed_research(), status=ResearchStatus.ENDED, research_id="r-ended")
    store.create(base)
    view = service.view_for("#/research/r-ended")
    assert view["status"] == "ended"
    blob = _visible_copy_chunks(view)
    assert "research_record" in blob
    assert blob.count("不能导出 strategy_pack") <= 1
