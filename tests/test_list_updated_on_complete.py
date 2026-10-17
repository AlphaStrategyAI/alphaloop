from datetime import UTC, datetime, timedelta
from pathlib import Path

from engine.research.clock import TimeBudget
from engine.research.loop import ResearchLoop
from engine.research.store import SQLiteStore
from tests.test_loop_runtime import NOW, PassReviewer, running_research, FakeBuilder, report


class PassBuilder(FakeBuilder):
    def build(self, research, attempt_number: int):
        draft = super().build(research, attempt_number)
        from dataclasses import replace as dreplace

        return dreplace(draft, attempt=dreplace(draft.attempt, verification=report(True)))


def test_complete_bumps_updated_at(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "upd.db")
    store.create(running_research())
    before = store.load("r-loop").updated_at
    loop = ResearchLoop(
        store,
        PassBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW + timedelta(seconds=30),
    )
    after = loop.run_once("r-loop")
    assert after.updated_at >= before + timedelta(seconds=1)
    listed = store.list_research()[0].updated_at
    assert listed == after.updated_at
