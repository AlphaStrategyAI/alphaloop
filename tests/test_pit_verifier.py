"""Tests for PIT consistency verifier and fourth export gate (B1)."""
from datetime import UTC, datetime

from engine.export import strategy_pack_eligibility
from engine.research.models import (
    Attempt,
    ChangeClass,
    Research,
    ResearchBrief,
    ResearchStatus,
    ReviewReport,
    ImplementationDelta,
    LogicStatement,
    RoundV2,
    Slot,
    TrialCounters,
    Version,
)
from datetime import date

from engine.metrics import SimulationReport
from engine.research.models import AssetClass, Market, MethodRef, Universe
from engine.strategy import StrategySpec
from engine.verifiers import (
    PIT_VERIFIER_REVISION,
    PitVerifierResult,
    VerificationReport,
    VerifierResult,
    _pit_consistency,
    method_set_excluding_pit,
    run_verifiers,
)


def test_pit_verifier_revision_is_preset() -> None:
    assert "pit.consistency" in PIT_VERIFIER_REVISION
    assert PIT_VERIFIER_REVISION["pit.consistency"]["category"] == "时点/前视一致性"


def test_pit_consistency_passes_when_all_evidence_before_cutoff() -> None:
    result = _pit_consistency(
        spec=None,
        evidence_timestamps=[
            ("ev-1", "2024-01-15"),
            ("ev-2", "2024-06-01"),
        ],
        backtest_cutoff="2024-12-31",
    )
    assert result.passed is True
    assert result.violations == ()
    assert result.verifier_id == "pit.consistency"


def test_pit_consistency_fails_when_evidence_after_cutoff() -> None:
    result = _pit_consistency(
        spec=None,
        evidence_timestamps=[
            ("ev-1", "2024-01-15"),
            ("ev-2", "2025-03-01"),
        ],
        backtest_cutoff="2024-12-31",
    )
    assert result.passed is False
    assert len(result.violations) == 1
    assert "ev-2" in result.violations[0]


def test_pit_consistency_empty_evidence_passes() -> None:
    result = _pit_consistency(
        spec=None,
        evidence_timestamps=[],
        backtest_cutoff="2024-12-31",
    )
    assert result.passed is True
    assert result.violations == ()


def test_pit_consistency_multiple_violations() -> None:
    result = _pit_consistency(
        spec=None,
        evidence_timestamps=[
            ("ev-1", "2025-01-01"),
            ("ev-2", "2025-02-01"),
            ("ev-3", "2024-06-01"),
        ],
        backtest_cutoff="2024-12-31",
    )
    assert result.passed is False
    assert len(result.violations) == 2
    assert any("ev-1" in v for v in result.violations)
    assert any("ev-2" in v for v in result.violations)


def _mock_attempt_with_pit(pit_passed: bool) -> Attempt:
    pit_result = PitVerifierResult(
        verifier_id="pit.consistency",
        revision="pit-v1",
        passed=pit_passed,
        values={"violations_count": 0.0 if pit_passed else 1.0},
        rule="test",
        evidence_timestamps=(),
        backtest_cutoff="2024-12-31",
        violations=() if pit_passed else ("ev-1 dated 2025-01-01 > cutoff 2024-12-31",),
    )
    scorecard = VerifierResult(
        verifier_id="scorecard.market",
        revision="scorecard-v1",
        passed=True,
        values={},
        rule="test",
    )
    return Attempt(
        attempt_id="a-1",
        number=1,
        change_class=ChangeClass.PARAM,
        spec=None,
        simulation=None,
        verification=VerificationReport(results=(scorecard, pit_result)),
        review=ReviewReport(passed=True, findings=()),
    )


def _completed_research_with_pit(pit_passed: bool) -> Research:
    now = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    attempt = _mock_attempt_with_pit(pit_passed)
    round_ = RoundV2(
        round_id="v1-r1",
        number=1,
        accepted_attempt=attempt,
        completed_at=now,
        logic_statement=LogicStatement("test", False, baseline_version=1),
        implementation_delta=ImplementationDelta(),
        trial_counters=TrialCounters(1, 1, 1),
    )
    version = Version(
        version_id="v-1",
        number=1,
        brief_snapshot=ResearchBrief(
            thesis=Slot("test", True),
            universe=Slot(None, True),
            max_effective_hours=Slot(12.0, True),
            round1_methods=Slot((), True),
            coverage_floor=Slot(None, True),
        ),
        rounds=(round_,),
        opened_at=now,
        opened_by="confirm_run",
    )
    return Research(
        research_id="r-1",
        status=ResearchStatus.COMPLETED,
        brief=ResearchBrief(),
        versions=(version,),
        current_version_number=1,
        pending_confirm=None,
        consecutive_review_failures=0,
        effective_seconds=3600.0,
        export_eligible=True,
        created_at=now,
        updated_at=now,
    )


def test_fourth_gate_pit_executed_and_passed_required() -> None:
    research_pit_passed = _completed_research_with_pit(pit_passed=True)
    research_pit_failed = _completed_research_with_pit(pit_passed=False)

    eligible = strategy_pack_eligibility(research_pit_passed)
    not_eligible = strategy_pack_eligibility(research_pit_failed)

    assert eligible.eligible is True
    assert "pit_executed_and_passed" not in eligible.failed_checks

    assert not_eligible.eligible is False
    assert "pit_executed_and_passed" in not_eligible.failed_checks


def test_fourth_gate_pit_not_executed() -> None:
    """Test that missing PIT verification fails the fourth gate."""
    now = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    scorecard = VerifierResult(
        verifier_id="scorecard.market",
        revision="scorecard-v1",
        passed=True,
        values={},
        rule="test",
    )
    attempt = Attempt(
        attempt_id="a-1",
        number=1,
        change_class=ChangeClass.PARAM,
        spec=None,
        simulation=None,
        verification=VerificationReport(results=(scorecard,)),
        review=ReviewReport(passed=True, findings=()),
    )
    round_ = RoundV2(
        round_id="v1-r1",
        number=1,
        accepted_attempt=attempt,
        completed_at=now,
        logic_statement=LogicStatement("test", False, baseline_version=1),
        implementation_delta=ImplementationDelta(),
        trial_counters=TrialCounters(1, 1, 1),
    )
    version = Version(
        version_id="v-1",
        number=1,
        brief_snapshot=ResearchBrief(
            thesis=Slot("test", True),
            universe=Slot(None, True),
            max_effective_hours=Slot(12.0, True),
            round1_methods=Slot((), True),
            coverage_floor=Slot(None, True),
        ),
        rounds=(round_,),
        opened_at=now,
        opened_by="confirm_run",
    )
    research = Research(
        research_id="r-1",
        status=ResearchStatus.COMPLETED,
        brief=ResearchBrief(),
        versions=(version,),
        current_version_number=1,
        pending_confirm=None,
        consecutive_review_failures=0,
        effective_seconds=3600.0,
        export_eligible=True,
        created_at=now,
        updated_at=now,
    )
    
    eligibility = strategy_pack_eligibility(research)
    assert eligibility.eligible is False
    assert "pit_executed_and_passed" in eligibility.failed_checks


def test_eligibility_has_all_four_gates() -> None:
    """Test that ExportEligibility reports all four gates correctly."""
    research_pit_passed = _completed_research_with_pit(pit_passed=True)
    eligibility = strategy_pack_eligibility(research_pit_passed)
    
    assert eligibility.eligible is True
    assert eligibility.failed_checks == ()
    
    failed_gates = {"completed", "all_current_methods_passed", "no_pending_confirm", 
                    "all_reverifies_passed", "pit_executed_and_passed"}
    for gate in failed_gates:
        assert gate not in eligibility.failed_checks


def _passing_report(end: date | None = date(2024, 12, 31)) -> SimulationReport:
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
        start=date(2020, 1, 2),
        end=end,
    )


def _spec() -> StrategySpec:
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("SPY",))
    return StrategySpec(
        id="pit-spec",
        thesis_locked="mean reversion",
        universe=universe,
        frequency="1d",
        side="long_only",
        method_set=(
            MethodRef("overfit.walk", "walk-v1"),
            MethodRef("stability.oos", "stability-v1"),
        ),
        model_family="mean_reversion",
        lookback_days=20,
        entry_z=1.0,
    )


def test_run_verifiers_emits_pit_consistency() -> None:
    report = _passing_report()
    spec = _spec()
    verification = run_verifiers(
        report,
        spec,
        evidence_as_of=(("ev-1", "2024-06-01"),),
    )
    pit = next(item for item in verification.results if item.verifier_id == "pit.consistency")
    assert pit.passed is True
    failed_end = run_verifiers(_passing_report(end=None), spec)
    pit_none = next(
        item for item in failed_end.results if item.verifier_id == "pit.consistency"
    )
    assert pit_none.passed is False
    missing = run_verifiers(
        report,
        spec,
        missing_as_of_material_ids=("local-md",),
    )
    pit_missing = next(
        item for item in missing.results if item.verifier_id == "pit.consistency"
    )
    assert pit_missing.passed is False
    method_set = method_set_excluding_pit(spec.method_set)
    assert verification.passed_for(method_set) is True
    assert missing.passed_for(method_set) is True
    assert missing.passed is False


def test_pit_consistency_verifier_is_in_presets() -> None:
    """Ensure pit.consistency is available as a preset verifier."""
    assert "pit.consistency" in PIT_VERIFIER_REVISION
    pit_config = PIT_VERIFIER_REVISION["pit.consistency"]
    assert pit_config["revision"] == "pit-v1"
    assert pit_config["category"] == "时点/前视一致性"
    assert "dimensions" in pit_config
    assert pit_config["dimensions"][0]["kind"] == "pit_consistency"
