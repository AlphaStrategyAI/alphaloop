from dataclasses import replace
from datetime import UTC, date, datetime
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
    ResearchEvent,
    ResearchStatus,
    ReviewReport,
    RoundDraft,
    Slot,
    Universe,
    Version,
    new_research,
)
from engine.research.state_machine import transition
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
        start=date(2014, 1, 2),
        end=date(2016, 12, 30),
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
        version = research.current_version_number or 1
        attempt = Attempt(
            attempt_id=f"a-{version}-{attempt_number}",
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


def test_three_technical_review_failures_stay_running_without_a_round(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    store.create(running_research())
    loop = ResearchLoop(store, FakeBuilder(), FailReviewer(), TimeBudget(lambda: 10.0), lambda: NOW)

    result = loop.run_once("r-loop")

    assert result.status is ResearchStatus.RUNNING
    assert result.pending_confirm is None
    assert result.current_version_number == 1
    assert result.versions[0].rounds == ()
    assert store.last_completed_round("r-loop") == 0
    assert store.review_failure_count("r-loop", 1, 1) == 3


def test_reload_with_three_persisted_failures_resets_and_retries_while_budget_remains(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    store.create(running_research())
    for number in range(1, 4):
        store.record_review_attempt(
            "r-loop",
            1,
            1,
            Attempt(
                attempt_id=f"a-{number}",
                number=number,
                change_class=ChangeClass.PARAM,
                spec=strategy(number),
                simulation=simulation(),
                verification=report(),
                review=ReviewReport(False, (), "choose a different automatic change"),
            ),
            NOW,
        )
    assert store.load("r-loop").status is ResearchStatus.RUNNING
    assert store.review_failure_count("r-loop", 1, 1) == 3

    builder = FakeBuilder()
    result = ResearchLoop(
        store,
        builder,
        FailReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")

    assert result.status is ResearchStatus.RUNNING
    assert result.pending_confirm is None
    assert result.versions[0].rounds == ()
    assert store.last_completed_round("r-loop") == 0
    assert builder.calls >= 1
    assert result.consecutive_review_failures == 3


def test_three_technical_failures_with_exhausted_budget_end(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    research = replace(
        running_research(),
        brief=replace(running_research().brief, max_effective_hours=Slot(1.0, True)),
        effective_seconds=3600.0,
    )
    store.create(research)
    for number in range(1, 4):
        store.record_review_attempt(
            "r-loop",
            1,
            1,
            Attempt(
                attempt_id=f"a-{number}",
                number=number,
                change_class=ChangeClass.PARAM,
                spec=strategy(number),
                simulation=simulation(),
                verification=report(),
                review=ReviewReport(False, (), "choose a different automatic change"),
            ),
            NOW,
        )
    builder = FakeBuilder()
    result = ResearchLoop(
        store,
        builder,
        FailReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert result.status is ResearchStatus.ENDED
    assert result.pending_confirm is None
    assert builder.calls == 0


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


class InFloorShrinkBuilder(FakeBuilder):
    def build(self, research, attempt_number: int) -> RoundDraft:
        self.calls += 1
        round_number = len(research.versions[0].rounds) + 1
        if round_number == 1:
            covered_assets, years, missing_pct, passed = 10, 10.0, 2.0, False
        else:
            covered_assets, years, missing_pct, passed = 9, 9.0, 4.0, True
        attempt = Attempt(
            attempt_id=f"a-{round_number}-{attempt_number}",
            number=attempt_number,
            change_class=ChangeClass.PARAM,
            spec=strategy(attempt_number),
            simulation=replace(
                simulation(),
                covered_assets=covered_assets,
                observations=int(years * 252),
                missing_pct=missing_pct,
            ),
            verification=report(passed),
            review=None,
        )
        return RoundDraft(1, round_number, attempt)


def test_in_floor_shrink_across_rounds_is_recorded_and_can_complete(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    research = running_research()
    symbols = tuple(f"S{i}" for i in range(10))
    research = replace(
        research,
        brief=replace(
            research.brief,
            universe=Slot(
                Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, symbols),
                True,
            ),
            coverage_floor=Slot(CoverageFloor(8, 8, 8.0), True),
        ),
    )
    store.create(research)
    loop = ResearchLoop(
        store,
        InFloorShrinkBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    )

    first = loop.run_once("r-loop")
    assert first.status is ResearchStatus.RUNNING
    assert first.coverage_history == ()
    assert first.last_coverage is not None
    assert len(first.last_coverage.assets) == 10

    second = loop.run_once("r-loop")
    assert len(second.coverage_history) == 1
    shrink = second.coverage_history[0]
    assert shrink.within_floor is True
    assert len(shrink.before.assets) == 10
    assert len(shrink.after.assets) == 9
    assert second.status is ResearchStatus.COMPLETED
    assert second.pending_confirm is None


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
    assert waiting.pending_confirm.patch
    assert waiting.pending_confirm.patch[0][0] == "coverage_floor"
    assert waiting.last_coverage is not None
    assert waiting.last_coverage.start == date(2014, 1, 2)
    assert waiting.last_coverage.end == date(2016, 12, 30)

    approved = transition(waiting, ResearchEvent.CONFIRM_APPROVE, NOW)
    observed_floor = waiting.pending_confirm.patch[0][1]
    assert approved.brief.coverage_floor.value == observed_floor
    store.save(approved, waiting.updated_at)

    continued = ResearchLoop(
        store,
        FakeBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert continued.brief.coverage_floor.value == observed_floor
    assert continued.pending_confirm is None or continued.pending_confirm.kind is not ConfirmKind.COVERAGE


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
