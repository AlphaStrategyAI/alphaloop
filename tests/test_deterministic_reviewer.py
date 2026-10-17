from dataclasses import replace
from datetime import UTC, date, datetime

from engine.metrics import SimulationReport
from engine.research.models import (
    AssetClass,
    Attempt,
    ChangeClass,
    Market,
    MethodRef,
    RoundDraft,
    Universe,
)
from engine.review.deterministic import DeterministicReviewer, default_v1_pass
from engine.strategy import StrategySpec
from engine.verifiers import PitVerifierResult, VerificationReport, VerifierResult, run_verifiers

NOW = datetime(2026, 10, 13, tzinfo=UTC)


def _simulation() -> SimulationReport:
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


def _spec(family: str = "mean_reversion") -> StrategySpec:
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("SPY",))
    methods = (
        MethodRef("overfit.walk", "walk-v1"),
        MethodRef("stability.oos", "stability-v1"),
    )
    return StrategySpec(
        id="det-review",
        thesis_locked="reversal",
        universe=universe,
        frequency="1d",
        side="long_only",
        method_set=methods,
        model_family=family,
        lookback_days=20,
        entry_z=1.0,
    )


def _draft(pit_passed: bool, methods_pass: bool = True) -> RoundDraft:
    spec = _spec()
    report = _simulation()
    verification = run_verifiers(
        report,
        spec,
        evidence_as_of=(("ev-1", "2016-01-01"),) if pit_passed else (),
        missing_as_of_material_ids=() if pit_passed else ("ev-1",),
    )
    if not methods_pass:
        verification = VerificationReport(
            tuple(
                replace(item, passed=False) if item.verifier_id == "overfit.walk" else item
                for item in verification.results
            )
        )
    attempt = Attempt(
        attempt_id="a-1",
        number=1,
        change_class=ChangeClass.PARAM,
        spec=spec,
        simulation=report,
        verification=verification,
    )
    return RoundDraft(1, 1, attempt)


def test_deterministic_reviewer_passes_when_methods_pass_even_if_pit_failed() -> None:
    draft = _draft(pit_passed=False, methods_pass=True)
    report = DeterministicReviewer(default_v1_pass).run(draft)
    assert report.passed is True
    assert report.findings == ()


def test_deterministic_reviewer_passes_when_method_set_failed_for_mean_reversion() -> None:
    draft = _draft(pit_passed=True, methods_pass=False)
    report = DeterministicReviewer(default_v1_pass).run(draft)
    assert report.passed is True


def test_deterministic_reviewer_fails_for_non_mean_reversion_family() -> None:
    draft = _draft(pit_passed=True)
    draft = replace(
        draft,
        attempt=replace(draft.attempt, spec=_spec(family="momentum")),
    )
    report = DeterministicReviewer(default_v1_pass).run(draft)
    assert report.passed is False
