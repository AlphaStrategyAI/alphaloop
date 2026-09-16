from datetime import UTC, date, datetime

from engine.research.coverage import CoverageDecision, decide_coverage, within_floor
from engine.research.models import ConfirmKind, CoverageFloor, CoverageSnapshot

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
FLOOR = CoverageFloor(min_assets=8, min_years=8, max_missing_pct=8.0)


def snap(assets: int, years: float, missing: float) -> CoverageSnapshot:
    return CoverageSnapshot(
        assets=tuple(f"S{i}" for i in range(assets)),
        years=years,
        missing_pct=missing,
        start=date(2010, 1, 1),
        end=date(2020, 1, 1),
        as_of=NOW,
    )


def test_within_floor_is_inclusive_of_the_locked_minimums() -> None:
    assert within_floor(snap(8, 8.0, 8.0), FLOOR)
    assert not within_floor(snap(7, 8.0, 8.0), FLOOR)
    assert not within_floor(snap(8, 7.9, 8.0), FLOOR)
    assert not within_floor(snap(8, 8.0, 8.1), FLOOR)


def test_shrink_inside_floor_is_recorded_and_does_not_confirm() -> None:
    previous = snap(10, 10.0, 2.0)
    observed = snap(9, 9.0, 4.0)
    decision = decide_coverage(previous, observed, FLOOR, version_number=1, round_number=2)
    assert decision.action == "record_shrink"
    assert decision.shrink is not None
    assert decision.shrink.within_floor is True
    assert decision.shrink.reason
    assert decision.request is None


def test_unchange_inside_floor_continues_without_a_shrink_row() -> None:
    observed = snap(10, 10.0, 2.0)
    decision = decide_coverage(observed, observed, FLOOR, 1, 1)
    assert decision.action == "continue"
    assert decision.shrink is None
    assert decision.request is None


def test_breach_confirms_and_never_auto_lowers_the_floor() -> None:
    previous = snap(10, 10.0, 2.0)
    observed = snap(3, 4.0, 20.0)
    decision = decide_coverage(previous, observed, FLOOR, 2, 3)
    assert decision.action == "confirm"
    assert decision.request is not None
    assert decision.request.kind is ConfirmKind.COVERAGE
    assert decision.shrink is not None
    assert decision.shrink.within_floor is False
    assert decision.request.patch == ()
