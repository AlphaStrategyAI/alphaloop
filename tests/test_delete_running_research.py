"""Deleting a research that is still running must not KeyError or stop the engine."""

from __future__ import annotations

import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest

from engine.main import ResearchCommandService
from engine.research.clock import TimeBudget
from engine.research.loop import ResearchLoop
from engine.research.market_data_cancel import (
    begin_market_data_generation,
    end_market_data_generation,
    generation_is_cancelled,
    raise_if_market_data_cancelled,
)
from engine.research.models import ResearchStatus
from engine.research.removal import ResearchRemoved
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from tests.test_loop_runtime import NOW, FakeBuilder, PassReviewer, running_research


def _loop(store: SQLiteStore, builder: FakeBuilder) -> ResearchLoop:
    return ResearchLoop(
        store,
        builder,
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    )


def test_run_once_after_delete_does_not_raise_keyerror(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    research = running_research()
    store.create(research)
    store.delete(research.research_id)
    loop = _loop(store, FakeBuilder())

    try:
        loop.run_once(research.research_id)
    except ResearchRemoved:
        return
    except KeyError as exc:
        raise AssertionError(
            f"run_once raised KeyError for a deleted research: {exc}"
        ) from exc


class _CancelAwareBuilder(FakeBuilder):
    """Blocks inside the round until delete cancels this research's in-flight work."""

    def __init__(self, research_id: str, started: threading.Event) -> None:
        super().__init__()
        self.research_id = research_id
        self.started = started

    def build(self, research, attempt_number: int):
        if research.research_id != self.research_id:
            return super().build(research, attempt_number)
        generation, token = begin_market_data_generation()
        try:
            self.started.set()
            deadline = time.monotonic() + 3.0
            while not generation_is_cancelled(generation):
                if time.monotonic() > deadline:
                    raise AssertionError(
                        "delete did not cancel in-flight work for the running research"
                    )
                time.sleep(0.01)
            raise_if_market_data_cancelled()
        finally:
            end_market_data_generation(token)
        raise AssertionError("cancelled market-data load must not continue the round")


def test_delete_while_running_keeps_the_engine_alive(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    loop_store = SQLiteStore(database)
    victim = running_research()
    keeper = replace(running_research(), research_id="r-keep")
    loop_store.create(victim)
    loop_store.create(keeper)

    started = threading.Event()
    builder = _CancelAwareBuilder(victim.research_id, started)
    loop = _loop(loop_store, builder)
    service = ResearchCommandService(
        SQLiteStore(database),
        EnginePaths.for_colocated_root(tmp_path),
    )
    from engine.main import advance_running_research

    errors: list[BaseException] = []

    def tick() -> None:
        try:
            for research_id in ("r-loop", "r-keep"):
                advance_running_research(loop_store, loop, research_id)
        except BaseException as exc:  # noqa: BLE001 - the regression is any crash
            errors.append(exc)

    worker = threading.Thread(target=tick, name="engine-tick")
    worker.start()
    assert started.wait(2.0), "running research did not enter in-flight work"
    service.handle({"type": "delete_research", "research_id": victim.research_id})
    worker.join(5.0)

    assert not worker.is_alive(), "engine tick did not return after delete"
    assert errors == [], f"engine tick crashed: {errors!r}"
    advance_running_research(loop_store, loop, victim.research_id)
    kept = loop_store.load("r-keep")
    assert kept.status is ResearchStatus.COMPLETED
    with pytest.raises(KeyError):
        loop_store.load(victim.research_id)
