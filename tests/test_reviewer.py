from datetime import UTC, datetime

from engine.research.models import (
    AssetClass,
    Attempt,
    ChangeClass,
    Market,
    RoundDraft,
    Universe,
)
from engine.review.subagent import (
    FROZEN_REVIEW_RUBRIC,
    MAX_CONSECUTIVE_REVIEW_FAILURES,
    LLMPort,
    SubagentReviewer,
    run_review_gate,
)
from engine.strategy import StrategySpec
from engine.verifiers import VerificationReport

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


class SequenceLLM(LLMPort):
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.responses.pop(0)


def draft(number: int = 1) -> RoundDraft:
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA",))
    spec = StrategySpec(
        id=f"s-{number}",
        thesis_locked="reversal",
        universe=universe,
        frequency="1d",
        side="long_only",
        method_set=(),
        model_family="mean_reversion",
        lookback_days=20 + number,
        entry_z=1.0,
    )
    attempt = Attempt(
        attempt_id=f"a-{number}",
        number=number,
        change_class=ChangeClass.PARAM,
        spec=spec,
        simulation=object(),  # type: ignore[arg-type]
        verification=VerificationReport(()),
        review=object(),  # type: ignore[arg-type]
    )
    return RoundDraft(version_number=1, round_number=1, attempt=attempt)


def test_frozen_rubric_names_all_non_negotiable_checks() -> None:
    assert "lookahead bias" in FROZEN_REVIEW_RUBRIC
    assert "economic-logic drift" in FROZEN_REVIEW_RUBRIC
    assert "data-snooping" in FROZEN_REVIEW_RUBRIC
    assert "benchmark mismatch" in FROZEN_REVIEW_RUBRIC


def test_second_llm_result_has_exact_review_shape() -> None:
    llm = SequenceLLM(
        ['{"passed":false,"findings":[{"code":"lookahead","message":"future data"}],"required_changes":"lag the signal"}']
    )
    report = SubagentReviewer(llm).run(draft())
    assert report.passed is False
    assert report.findings[0].code == "lookahead"
    assert report.required_changes == "lag the signal"
    assert llm.calls[0][0] == FROZEN_REVIEW_RUBRIC


def test_a_passed_retry_creates_one_round_under_same_version() -> None:
    llm = SequenceLLM(
        [
            '{"passed":false,"findings":[{"code":"snoop","message":"tuned on OOS"}],"required_changes":"freeze OOS"}',
            '{"passed":true,"findings":[]}',
        ]
    )
    reviewer = SubagentReviewer(llm)

    outcome = run_review_gate(
        draft(),
        reviewer,
        lambda prior, report: draft(prior.attempt.number + 1),
        NOW,
    )

    assert outcome.successful_round is not None
    assert outcome.successful_round.number == 1
    assert outcome.successful_round.accepted_attempt.number == 2
    assert outcome.confirm_request is None
    assert len(outcome.attempts) == 2


def test_three_failures_never_create_a_round_or_advance_version() -> None:
    failed = (
        '{"passed":false,"findings":[{"code":"benchmark","message":"mismatch"}],'
        '"required_changes":"use locked benchmark"}'
    )
    reviewer = SubagentReviewer(SequenceLLM([failed, failed, failed]))

    outcome = run_review_gate(
        draft(),
        reviewer,
        lambda prior, report: draft(prior.attempt.number + 1),
        NOW,
    )

    assert MAX_CONSECUTIVE_REVIEW_FAILURES == 3
    assert outcome.successful_round is None
    assert len(outcome.attempts) == 3
    assert {item.spec.id for item in outcome.attempts} == {"s-1", "s-2", "s-3"}
    assert outcome.confirm_request is not None
    assert outcome.confirm_request.kind.value == "review_blocked"
    assert outcome.version_number == 1


def test_restart_with_two_persisted_failures_runs_only_attempt_three() -> None:
    failed = (
        '{"passed":false,"findings":[{"code":"lookahead","message":"future data"}],'
        '"required_changes":"lag inputs"}'
    )
    recorded: list[Attempt] = []
    outcome = run_review_gate(
        draft(3),
        SubagentReviewer(SequenceLLM([failed])),
        lambda prior, report: draft(prior.attempt.number + 1),
        NOW,
        prior_failures=2,
        on_attempt=recorded.append,
    )
    assert [attempt.number for attempt in recorded] == [3]
    assert outcome.successful_round is None
    assert outcome.confirm_request is not None
