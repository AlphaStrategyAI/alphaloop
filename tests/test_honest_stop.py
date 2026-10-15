"""Implementation trial budget and honest completion (V1 P0)."""

from dataclasses import replace
from pathlib import Path

import pytest

from engine.research.clock import TimeBudget
from engine.research.honest_stop import (
    budget_exhausted_stop,
    change_requires_user_confirm,
    completed_presentation,
    max_implementation_trials,
    running_budget_hint,
    trial_budget_view,
    verification_thresholds_unchanged,
)
from engine.research.loop import ResearchLoop
from engine.research.models import ResearchEvent, ResearchStatus
from engine.research.specify import ProposedChange
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.verifiers import VERIFIER_REVISIONS
from tests.test_loop_runtime import (
    NOW,
    EconomicBuilder,
    FailedMethodsParamBuilder,
    PassReviewer,
    running_research,
)


def test_change_requires_user_confirm_distinguishes_logic_model_from_impl() -> None:
    assert change_requires_user_confirm(
        ProposedChange("max_drawdown_floor", -0.25, -0.35)
    )
    assert change_requires_user_confirm(
        ProposedChange("signal_definition", "a", "b")
    )
    assert not change_requires_user_confirm(
        ProposedChange("lookback_days", 20, 25)
    )
    assert not change_requires_user_confirm(
        ProposedChange("model_family", "mean_reversion", "momentum")
    )


def test_max_implementation_trials_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "7")
    assert max_implementation_trials() == 7


def test_completed_presentation_budget_exhausted_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "1")
    store = SQLiteStore(tmp_path / "h.db")
    store.create(running_research())
    completed = ResearchLoop(
        store,
        FailedMethodsParamBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    pres = completed_presentation(completed)
    assert pres.budget_exhausted is True
    assert pres.trial_budget.used == 1
    assert pres.trial_budget.budget == 1
    assert pres.hint_line == ""
    assert "预算已用尽" in pres.summary
    assert "research_record" in pres.summary


def test_auto_continues_within_budget_then_completes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "3")
    store = SQLiteStore(tmp_path / "budget.db")
    store.create(running_research())
    loop = ResearchLoop(
        store,
        FailedMethodsParamBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    )
    first = loop.run_once("r-loop")
    assert first.status is ResearchStatus.RUNNING
    assert len(first.versions[0].rounds) == 1
    assert trial_budget_view(first).remaining == 2
    assert "自动迭代" in running_budget_hint(first)

    second = loop.run_once("r-loop")
    assert second.status is ResearchStatus.RUNNING
    assert len(second.versions[0].rounds) == 2

    third = loop.run_once("r-loop")
    assert third.status is ResearchStatus.COMPLETED
    assert len(third.versions[0].rounds) == 3
    assert budget_exhausted_stop(third)


def test_economic_change_still_confirms_with_high_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "99")
    store = SQLiteStore(tmp_path / "econ.db")
    store.create(running_research())
    waiting = ResearchLoop(
        store,
        EconomicBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert waiting.status is ResearchStatus.AWAITING_CONFIRM


def test_manual_continue_after_exhaustion_adds_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "1")
    monkeypatch.setenv("ALPHALOOP_TRIAL_BUDGET_INCREMENT", "2")
    store = SQLiteStore(tmp_path / "cont.db")
    store.create(running_research())
    loop = ResearchLoop(
        store,
        FailedMethodsParamBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    )
    completed = loop.run_once("r-loop")
    assert completed.status is ResearchStatus.COMPLETED
    round1 = completed.versions[0].rounds[0]
    floor_before = round1.accepted_attempt.spec.max_drawdown_floor
    v_before = round1.accepted_attempt.verification
    assert v_before is not None

    resumed = transition(
        replace(
            completed,
            implementation_trial_budget=completed.implementation_trial_budget + 2,
        ),
        ResearchEvent.CONTINUE_ITERATE,
        NOW,
    )
    store.save(resumed, completed.updated_at)
    after = loop.run_once("r-loop")
    assert len(after.versions[0].rounds) == 2
    assert after.versions[0].rounds[0].accepted_attempt.attempt_id == round1.accepted_attempt.attempt_id
    assert after.versions[0].rounds[1].accepted_attempt.spec.max_drawdown_floor == floor_before
    v_after = after.versions[0].rounds[1].accepted_attempt.verification
    assert v_after is not None
    assert verification_thresholds_unchanged(v_before, v_after)
    assert VERIFIER_REVISIONS["scorecard.market"]["default_max_drawdown_floor"] == -0.25
