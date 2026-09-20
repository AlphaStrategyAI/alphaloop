"""Tests for B6: Scorecard dimension schema and immutability."""
import pytest

from engine.research.methods import (
    DimensionSemanticChangeError,
    ScorecardDimension,
    ScorecardDimensionKind,
    validate_dimension_immutability,
)


def test_scorecard_dimension_kinds() -> None:
    assert ScorecardDimensionKind.PREDICTIVE_POWER == "predictive_power"
    assert ScorecardDimensionKind.STABILITY == "stability"
    assert ScorecardDimensionKind.PIT_CONSISTENCY == "pit_consistency"
    assert ScorecardDimensionKind.COST_SENSITIVITY == "cost_sensitivity"
    assert ScorecardDimensionKind.CROWDING == "crowding"
    assert ScorecardDimensionKind.CUSTOM == "custom"


def test_scorecard_dimension_fields() -> None:
    dim = ScorecardDimension(
        kind=ScorecardDimensionKind.PREDICTIVE_POWER,
        name="Sharpe Ratio OOS",
        description="Out-of-sample Sharpe ratio must exceed threshold",
        pass_threshold=0.5,
        comparison="gte",
        failure_display="Sharpe OOS {value} < {threshold}",
        unit="ratio",
    )
    assert dim.pass_threshold == 0.5
    assert dim.comparison == "gte"


def test_dimension_immutability_allows_new_dimensions() -> None:
    old_dims = (
        ScorecardDimension(
            kind=ScorecardDimensionKind.PREDICTIVE_POWER,
            name="Sharpe",
            description="OOS Sharpe",
            pass_threshold=0.5,
            comparison="gte",
            failure_display="fail",
        ),
    )
    new_dims = old_dims + (
        ScorecardDimension(
            kind=ScorecardDimensionKind.STABILITY,
            name="Stability",
            description="Return stability",
            pass_threshold=0.6,
            comparison="gte",
            failure_display="fail",
        ),
    )
    validate_dimension_immutability(old_dims, new_dims)


def test_dimension_immutability_rejects_semantic_change() -> None:
    old_dims = (
        ScorecardDimension(
            kind=ScorecardDimensionKind.PREDICTIVE_POWER,
            name="Sharpe",
            description="OOS Sharpe",
            pass_threshold=0.5,
            comparison="gte",
            failure_display="fail",
        ),
    )
    modified_dims = (
        ScorecardDimension(
            kind=ScorecardDimensionKind.PREDICTIVE_POWER,
            name="Sharpe",
            description="Changed: now measures IS Sharpe instead",
            pass_threshold=0.5,
            comparison="gte",
            failure_display="fail",
        ),
    )
    with pytest.raises(DimensionSemanticChangeError) as exc_info:
        validate_dimension_immutability(old_dims, modified_dims)
    assert "semantic" in str(exc_info.value).lower()


def test_dimension_immutability_rejects_threshold_change() -> None:
    old_dims = (
        ScorecardDimension(
            kind=ScorecardDimensionKind.PREDICTIVE_POWER,
            name="Sharpe",
            description="OOS Sharpe",
            pass_threshold=0.5,
            comparison="gte",
            failure_display="fail",
        ),
    )
    changed_threshold = (
        ScorecardDimension(
            kind=ScorecardDimensionKind.PREDICTIVE_POWER,
            name="Sharpe",
            description="OOS Sharpe",
            pass_threshold=0.8,
            comparison="gte",
            failure_display="fail",
        ),
    )
    with pytest.raises(DimensionSemanticChangeError):
        validate_dimension_immutability(old_dims, changed_threshold)


def test_dimension_immutability_rejects_comparison_change() -> None:
    old_dims = (
        ScorecardDimension(
            kind=ScorecardDimensionKind.PREDICTIVE_POWER,
            name="Sharpe",
            description="OOS Sharpe",
            pass_threshold=0.5,
            comparison="gte",
            failure_display="fail",
        ),
    )
    changed_comparison = (
        ScorecardDimension(
            kind=ScorecardDimensionKind.PREDICTIVE_POWER,
            name="Sharpe",
            description="OOS Sharpe",
            pass_threshold=0.5,
            comparison="gt",
            failure_display="fail",
        ),
    )
    with pytest.raises(DimensionSemanticChangeError):
        validate_dimension_immutability(old_dims, changed_comparison)


def test_dimension_immutability_allows_unit_change() -> None:
    """Unit is not a semantic field, so changes are allowed."""
    old_dims = (
        ScorecardDimension(
            kind=ScorecardDimensionKind.PREDICTIVE_POWER,
            name="Sharpe",
            description="OOS Sharpe",
            pass_threshold=0.5,
            comparison="gte",
            failure_display="fail",
            unit="ratio",
        ),
    )
    changed_unit = (
        ScorecardDimension(
            kind=ScorecardDimensionKind.PREDICTIVE_POWER,
            name="Sharpe",
            description="OOS Sharpe",
            pass_threshold=0.5,
            comparison="gte",
            failure_display="fail",
            unit="dimensionless",
        ),
    )
    validate_dimension_immutability(old_dims, changed_unit)


def test_empty_dimensions_valid() -> None:
    """Empty dimensions are valid (no existing dimensions to protect)."""
    validate_dimension_immutability((), ())
    validate_dimension_immutability(
        (),
        (
            ScorecardDimension(
                kind=ScorecardDimensionKind.PREDICTIVE_POWER,
                name="New",
                description="New dimension",
                pass_threshold=0.5,
                comparison="gte",
                failure_display="fail",
            ),
        ),
    )
