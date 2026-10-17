from dataclasses import replace
from pathlib import Path

from engine.research.clock import TimeBudget
from engine.research.loop import ResearchLoop
from engine.research.models import ResearchStatus
from engine.research.store import SQLiteStore
from tests.test_loop_runtime import FakeBuilder, FakeMonotonic, NOW, PassReviewer, running_research


class _AdvancingBuilder(FakeBuilder):
    def __init__(self, mono: FakeMonotonic) -> None:
        super().__init__()
        self._mono = mono

    def build(self, research, attempt_number: int):
        self._mono.value += 90.0
        return super().build(research, attempt_number)


def test_run_once_accumulates_effective_seconds_while_running(tmp_path: Path) -> None:
    mono = FakeMonotonic()
    store = SQLiteStore(tmp_path / "time.db")
    store.create(running_research())
    loop = ResearchLoop(
        store,
        _AdvancingBuilder(mono),
        PassReviewer(),
        TimeBudget(mono),
        lambda: NOW,
    )
    after = loop.run_once("r-loop")
    assert after.effective_seconds == 90.0
    assert store.load("r-loop").effective_seconds == 90.0


def test_budget_finish_rebegin_accumulates_idle_gap() -> None:
    mono = FakeMonotonic()
    budget = TimeBudget(mono)
    research = running_research()
    budget.begin(ResearchStatus.RUNNING)
    mono.value += 4.0
    research = budget.finish(research)
    assert research.effective_seconds == 4.0
    budget.begin(ResearchStatus.RUNNING)
    mono.value += 6.0
    research = budget.finish(research)
    assert research.effective_seconds == 10.0
