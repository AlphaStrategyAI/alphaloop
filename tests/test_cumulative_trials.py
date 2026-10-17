"""Cumulative rounds M, B5 late-pass, continue confirmation."""

import json
from dataclasses import replace
from pathlib import Path
import pytest

from engine.export import _round_history_with_trials, build_strategy_pack
from engine.main import ResearchCommandService
from engine.metrics import SimulationReport
from engine.research.clock import TimeBudget
from engine.research.data_window import (
    cumulative_rounds_on_window,
    late_pass_presentation,
)
from engine.research.honest_stop import (
    high_suspicion_round_threshold,
    validate_continue_iterate_confirm,
)
from engine.research.loop import ResearchLoop
from engine.research.models import ResearchEvent, ResearchStatus
from engine.research.runtime import EnginePaths
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.strategy import MarketPanel, MeanReversionStrategy
from tests.test_loop_runtime import (
    NOW,
    LogicSignalStopBuilder,
    PassReviewer,
    running_research,
    simulation,
    strategy,
)
from tests.test_loop_runtime import FakeBuilder, Attempt, ChangeClass, RoundDraft, report


class FailTwiceThenPassBuilder(FakeBuilder):
    def build(self, research, attempt_number: int) -> RoundDraft:
        draft = super().build(research, attempt_number)
        version_idx = (research.current_version_number or 1) - 1
        round_number = len(research.versions[version_idx].rounds) + 1
        passed = round_number >= 3
        spec = draft.attempt.spec
        if round_number >= 2:
            spec = replace(spec, lookback_days=20 + round_number * 5)
        attempt = replace(
            draft.attempt,
            spec=spec,
            verification=report(passed),
        )
        return replace(draft, attempt=attempt)


def test_logic_change_never_auto_continues_at_budget_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "1")
    store = SQLiteStore(tmp_path / "logic.db")
    store.create(running_research())
    waiting = ResearchLoop(
        store,
        LogicSignalStopBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert waiting.status is ResearchStatus.AWAITING_CONFIRM


def test_cumulative_m_across_versions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "5")
    store = SQLiteStore(tmp_path / "cross.db")
    store.create(running_research())
    loop = ResearchLoop(
        store,
        FailTwiceThenPassBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    )
    r = loop.run_once("r-loop")
    r = loop.run_once("r-loop")
    assert cumulative_rounds_on_window(r) == 2
    paused = transition(r, ResearchEvent.PAUSE, NOW)
    opened = transition(paused, ResearchEvent.MODIFY_CONFIRM, NOW)
    store.save(opened, r.updated_at)
    r = loop.run_once("r-loop")
    assert cumulative_rounds_on_window(r) == 3


def test_late_pass_after_third_round_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "5")
    store = SQLiteStore(tmp_path / "late.db")
    store.create(running_research())
    loop = ResearchLoop(
        store,
        FailTwiceThenPassBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    )
    current = loop.run_once("r-loop")
    current = loop.run_once("r-loop")
    current = loop.run_once("r-loop")
    assert current.status is ResearchStatus.COMPLETED
    assert cumulative_rounds_on_window(current) == 3
    late = late_pass_presentation(current)
    assert late is not None
    assert late["show"] is True
    assert late["cumulativeRoundsOnWindow"] == 3
    assert len(late["priorFailureRecords"]) == 2

    paths = EnginePaths.for_colocated_root(tmp_path)
    service = ResearchCommandService(store, paths)
    view = service.view_for("#/research/r-loop")
    assert view["cumulativeRoundsOnWindow"] == 3
    assert view["latePassPresentation"]["cumulativeRoundsOnWindow"] == 3
    prior = view["latePassPresentation"]["priorFailureRecords"]
    assert len(prior) == 2
    assert any(record["paramChanges"] for record in prior)
    second = next(record for record in prior if record["roundNumber"] >= 2)
    assert second["paramChanges"][0][0] == "回看天数"

    all_rounds = [round_ for version in current.versions for round_ in version.rounds]
    history = _round_history_with_trials(current, all_rounds)
    assert history["cumulative_rounds_on_window"] == 3
    assert len(history["rounds"]) == 3
    assert history["rounds"][0]["cumulative_round_on_window"] == 1
    assert history["rounds"][-1]["cumulative_round_on_window"] == 3
    assert any(item["implementation_delta"]["param_changes"] for item in history["rounds"])


def test_round_one_pass_no_late_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "5")

    class PassFirstBuilder(FakeBuilder):
        def build(self, research, attempt_number: int) -> RoundDraft:
            draft = super().build(research, attempt_number)
            return replace(draft, attempt=replace(draft.attempt, verification=report(True)))

    store = SQLiteStore(tmp_path / "r1.db")
    store.create(running_research())
    done = ResearchLoop(
        store,
        PassFirstBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert late_pass_presentation(done) is None


def test_continue_iterate_requires_confirm_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "1")
    store = SQLiteStore(tmp_path / "cont.db")
    paths = EnginePaths.for_colocated_root(tmp_path)
    service = ResearchCommandService(store, paths)
    store.create(running_research())
    completed = ResearchLoop(
        store,
        FailTwiceThenPassBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert completed.status is ResearchStatus.COMPLETED
    with pytest.raises(ValueError, match="user_confirmed"):
        service.handle(
            {"type": "continue_iterate", "research_id": "r-loop", "user_confirmed": False}
        )


def test_continue_high_suspicion_requires_second_ack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHALOOP_HIGH_SUSPICION_ROUNDS", "2")
    store = SQLiteStore(tmp_path / "m2.db")
    store.create(running_research())
    loop = ResearchLoop(
        store,
        FailTwiceThenPassBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    )
    research = loop.run_once("r-loop")
    research = loop.run_once("r-loop")
    research = replace(research, status=ResearchStatus.COMPLETED)
    assert cumulative_rounds_on_window(research) >= 2
    with pytest.raises(ValueError, match="high_suspicion_acknowledged"):
        validate_continue_iterate_confirm(
            research,
            user_confirmed=True,
            high_suspicion_acknowledged=False,
        )


def test_strategy_pack_rounds_json_includes_cumulative_m(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "5")
    store = SQLiteStore(tmp_path / "pack.db")
    store.create(running_research())
    loop = ResearchLoop(
        store,
        FailTwiceThenPassBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    )
    research = loop.run_once("r-loop")
    research = loop.run_once("r-loop")
    research = loop.run_once("r-loop")
    all_rounds = [r for v in research.versions for r in v.rounds]
    payload = _round_history_with_trials(research, all_rounds)
    assert payload["cumulative_rounds_on_window"] == 3
    assert payload["data_window_key"] is not None
    assert payload["rounds"][-1]["cumulative_round_on_window"] == 3
