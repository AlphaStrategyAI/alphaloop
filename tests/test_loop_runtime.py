from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from engine.metrics import SimulationReport
from engine.research.clock import TimeBudget
from engine.research.loop import ResearchLoop, RoundBuilder
from engine.research.models import (
    AssetClass,
    Attempt,
    ChangeClass,
    ConfirmKind,
    CoverageFloor,
    Market,
    ResearchStatus,
    ReviewReport,
    RoundDraft,
    Slot,
    Universe,
    Version,
    new_research,
)
from engine.research.runtime import EngineLock, RuntimePaths, read_live_owner
from engine.research.specify import ProposedChange
from engine.research.store import SQLiteStore
from engine.review.subagent import ReviewerPort
from engine.strategy import StrategySpec
from engine.verifiers import VerificationReport, VerifierResult

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


class FakeMonotonic:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


def report(passed: bool = True) -> VerificationReport:
    gate = VerifierResult(
        verifier_id="scorecard.market",
        revision="scorecard-v1",
        passed=passed,
        values={},
        rule="fixture",
    )
    return VerificationReport((gate, gate, gate, gate, gate))


def simulation() -> SimulationReport:
    return SimulationReport(
        r_total=0.2,
        r_ann=0.12,
        sharpe=0.9,
        vol_ann=0.13,
        max_drawdown=-0.2,
        benchmark_id="SPX",
        r_bench_ann=0.08,
        excess_ann=0.04,
        tracking_error=0.06,
        information_ratio=2 / 3,
        sharpe_oos=0.7,
        sharpe_is=1.0,
        oos_segment_returns=(0.02, 0.01, -0.005),
        top_20_crowding_sharpe_impact=0.01,
        annual_turnover=1.0,
        observations=756,
        covered_assets=1,
        missing_pct=0.0,
    )


def strategy(number: int) -> StrategySpec:
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA",))
    return StrategySpec(
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


class FakeBuilder(RoundBuilder):
    def __init__(self) -> None:
        self.calls = 0

    def build(self, research, attempt_number: int) -> RoundDraft:
        self.calls += 1
        attempt = Attempt(
            attempt_id=f"a-{attempt_number}",
            number=attempt_number,
            change_class=ChangeClass.PARAM,
            spec=strategy(attempt_number),
            simulation=simulation(),
            verification=report(),
            review=None,
        )
        return RoundDraft(1, 1, attempt)

    def retry(self, prior: RoundDraft, review: ReviewReport) -> RoundDraft:
        return self.build_for_retry(prior.attempt.number + 1)

    def build_for_retry(self, attempt_number: int) -> RoundDraft:
        return self.build(new_research("ignored", NOW), attempt_number)

    def next_change(self, accepted: Attempt) -> ProposedChange:
        return ProposedChange(
            "lookback_days",
            accepted.spec.lookback_days,
            accepted.spec.lookback_days + 5,
        )


class EconomicBuilder(FakeBuilder):
    def build(self, research, attempt_number: int) -> RoundDraft:
        draft = super().build(research, attempt_number)
        return replace(
            draft,
            attempt=replace(draft.attempt, verification=report(False)),
        )

    def next_change(self, accepted: Attempt) -> ProposedChange:
        return ProposedChange("max_drawdown_floor", -0.25, -0.30)


class PassReviewer(ReviewerPort):
    def run(self, round_draft: RoundDraft) -> ReviewReport:
        return ReviewReport(True, ())


class FailReviewer(ReviewerPort):
    def run(self, round_draft: RoundDraft) -> ReviewReport:
        return ReviewReport(False, (), "choose a different automatic change")


def running_research():
    research = new_research("r-loop", NOW)
    return replace(
        research,
        status=ResearchStatus.RUNNING,
        current_version_number=1,
        versions=(
            Version("r-loop-v1", 1, research.brief, (), NOW, "confirm_run"),
        ),
    )


def test_time_budget_ticks_only_while_running() -> None:
    monotonic = FakeMonotonic()
    clock = TimeBudget(monotonic)
    running = replace(running_research(), effective_seconds=5.0)
    clock.begin(ResearchStatus.RUNNING)
    monotonic.value = 107.5
    assert clock.finish(running).effective_seconds == 12.5

    paused = replace(running, status=ResearchStatus.PAUSED)
    clock.begin(paused.status)
    monotonic.value = 200.0
    assert clock.finish(paused).effective_seconds == 5.0


def test_passed_review_commits_round_and_completes(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    store.create(running_research())
    loop = ResearchLoop(store, FakeBuilder(), PassReviewer(), TimeBudget(lambda: 10.0), lambda: NOW)

    result = loop.run_once("r-loop")

    assert result.status is ResearchStatus.COMPLETED
    rounds = result.versions[0].rounds
    assert len(rounds) == 1
    accepted_review = rounds[0].accepted_attempt.review
    assert accepted_review is not None
    assert accepted_review.passed
    assert store.last_completed_round("r-loop") == 1


def test_three_review_failures_wait_without_round_or_version_advance(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    store.create(running_research())
    loop = ResearchLoop(store, FakeBuilder(), FailReviewer(), TimeBudget(lambda: 10.0), lambda: NOW)

    result = loop.run_once("r-loop")

    assert result.status is ResearchStatus.AWAITING_CONFIRM
    assert result.pending_confirm is not None
    assert result.pending_confirm.kind is ConfirmKind.REVIEW_BLOCKED
    assert result.current_version_number == 1
    assert result.versions[0].rounds == ()
    assert store.last_completed_round("r-loop") == 0
    assert store.review_failure_count("r-loop", 1, 1) == 3


def test_paused_loop_does_no_work_or_clock_charge(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    paused = replace(running_research(), status=ResearchStatus.PAUSED, effective_seconds=3.0)
    store.create(paused)
    builder = FakeBuilder()
    result = ResearchLoop(
        store,
        builder,
        PassReviewer(),
        TimeBudget(lambda: 99.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert result == paused
    assert builder.calls == 0
    assert result.effective_seconds == 3.0


def test_economic_next_change_waits_and_applies_only_after_approval(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    store.create(running_research())
    loop = ResearchLoop(
        store,
        EconomicBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    )

    waiting = loop.run_once("r-loop")

    assert waiting.status is ResearchStatus.AWAITING_CONFIRM
    assert waiting.current_version_number == 1
    assert waiting.pending_confirm is not None
    assert waiting.pending_confirm.kind is ConfirmKind.ECONOMIC
    assert waiting.pending_confirm.patch == (("max_drawdown_floor", -0.30),)


def test_coverage_below_any_locked_floor_dimension_waits(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    research = running_research()
    research = replace(
        research,
        brief=replace(
            research.brief,
            coverage_floor=Slot(CoverageFloor(2, 10, 0.0), True),
        ),
    )
    store.create(research)
    waiting = ResearchLoop(
        store,
        FakeBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert waiting.status is ResearchStatus.AWAITING_CONFIRM
    assert waiting.pending_confirm is not None
    assert waiting.pending_confirm.kind is ConfirmKind.COVERAGE


def test_sqlite_round_trip_and_heartbeat(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    research = running_research()
    store.create(research)
    assert store.load("r-loop") == research
    paths = RuntimePaths(tmp_path, tmp_path / "engine.lock", tmp_path / "owner.json")
    with EngineLock.acquire(paths, "cli") as lock:
        store.heartbeat(lock.owner, NOW)
        assert read_live_owner(paths) == lock.owner
        assert store.read_heartbeat().owner == "cli"
    assert read_live_owner(paths) is None
