"""V1-P0 transitional honest stop and manual continue."""

from pathlib import Path

from engine.research.clock import TimeBudget
from engine.research.honest_stop import (
    change_requires_user_confirm,
    completed_presentation,
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


def test_completed_presentation_for_failed_methods_is_not_success_copy(tmp_path: Path) -> None:
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
    assert pres.methods_verification_passed is False
    assert pres.export_kind == "research_record_only"
    assert "未通过" in pres.headline
    assert "research_record" in pres.summary
    assert pres.auto_iterate_declined is True
    assert pres.hint_line
    assert "未自动迭代" in pres.hint_line


def test_manual_continue_iterate_preserves_failed_round_and_thresholds(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
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
    assert not v_before.passed

    resumed = transition(completed, ResearchEvent.CONTINUE_ITERATE, NOW)
    store.save(resumed, completed.updated_at)
    after = loop.run_once("r-loop")

    assert len(after.versions[0].rounds) == 2
    assert after.versions[0].rounds[0].accepted_attempt.attempt_id == round1.accepted_attempt.attempt_id
    assert after.versions[0].rounds[1].number == 2
    assert after.versions[0].rounds[1].accepted_attempt.spec.max_drawdown_floor == floor_before
    assert (
        after.versions[0].rounds[1].accepted_attempt.spec.lookback_days
        > round1.accepted_attempt.spec.lookback_days
    )
    v_after = after.versions[0].rounds[1].accepted_attempt.verification
    assert v_after is not None
    assert verification_thresholds_unchanged(v_before, v_after)
    assert VERIFIER_REVISIONS["scorecard.market"]["default_max_drawdown_floor"] == -0.25
