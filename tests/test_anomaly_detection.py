"""Tests for B5: Anomaly detection with relative baseline."""

from engine.research.models import (
    ANOMALY_HEURISTIC_DEFAULTS,
    AnomalyBaseline,
    AnomalyHeuristic,
    AnomalyIndicator,
    detect_anomalies,
)


def test_anomaly_heuristic_defaults() -> None:
    """Test that default heuristics have expected values."""
    assert ANOMALY_HEURISTIC_DEFAULTS.sharpe_sigma_multiplier == 3.0
    assert ANOMALY_HEURISTIC_DEFAULTS.trial_count_multiplier == 2.0
    assert ANOMALY_HEURISTIC_DEFAULTS.recent_revision_days == 7


def test_anomaly_detection_uses_relative_baseline() -> None:
    """Sharpe outlier detection is relative to baseline, not absolute."""
    baseline = AnomalyBaseline(
        kind="prior_attempt",
        attempt_id="a-0",
        sharpe=1.0,
        sharpe_std=0.3,
        trial_count=5,
    )
    anomaly = detect_anomalies(
        sharpe=2.5,
        trial_count=6,
        coverage_shrunk=False,
        method_revision_age_days=30,
        baseline=baseline,
        heuristics=ANOMALY_HEURISTIC_DEFAULTS,
    )
    assert anomaly is not None
    assert AnomalyIndicator.SHARPE_OUTLIER in anomaly.indicators
    assert anomaly.baseline == baseline


def test_anomaly_detection_with_custom_heuristics() -> None:
    """Custom heuristics change detection thresholds (not iron rules)."""
    baseline = AnomalyBaseline(
        kind="prior_attempt",
        sharpe=1.0,
        sharpe_std=0.3,
        trial_count=5,
    )
    custom_heuristics = AnomalyHeuristic(
        sharpe_sigma_multiplier=5.0,
        trial_count_multiplier=3.0,
        recent_revision_days=3,
    )
    anomaly = detect_anomalies(
        sharpe=2.5,
        trial_count=14,
        coverage_shrunk=False,
        method_revision_age_days=30,
        baseline=baseline,
        heuristics=custom_heuristics,
    )
    assert anomaly is None or AnomalyIndicator.SHARPE_OUTLIER not in anomaly.indicators


def test_anomaly_detection_flags_high_trial_count() -> None:
    """High trial count relative to baseline is flagged."""
    baseline = AnomalyBaseline(
        kind="prior_attempt",
        sharpe=1.0,
        trial_count=5,
    )
    anomaly = detect_anomalies(
        sharpe=1.0,
        trial_count=15,
        coverage_shrunk=False,
        method_revision_age_days=30,
        baseline=baseline,
        heuristics=ANOMALY_HEURISTIC_DEFAULTS,
    )
    assert anomaly is not None
    assert AnomalyIndicator.HIGH_TRIAL_COUNT in anomaly.indicators


def test_anomaly_detection_flags_coverage_shrunk() -> None:
    """Coverage shrinkage is always flagged (not a heuristic)."""
    baseline = AnomalyBaseline(
        kind="prior_attempt",
        sharpe=1.0,
        trial_count=5,
    )
    anomaly = detect_anomalies(
        sharpe=1.0,
        trial_count=5,
        coverage_shrunk=True,
        method_revision_age_days=30,
        baseline=baseline,
    )
    assert anomaly is not None
    assert AnomalyIndicator.COVERAGE_SHRUNK in anomaly.indicators


def test_anomaly_detection_flags_recent_method_revision() -> None:
    """Recent method revision is flagged."""
    baseline = AnomalyBaseline(
        kind="prior_attempt",
        sharpe=1.0,
        trial_count=5,
    )
    anomaly = detect_anomalies(
        sharpe=1.0,
        trial_count=5,
        coverage_shrunk=False,
        method_revision_age_days=3,
        baseline=baseline,
    )
    assert anomaly is not None
    assert AnomalyIndicator.RECENT_METHOD_REVISION in anomaly.indicators


def test_anomaly_detection_returns_none_when_no_anomalies() -> None:
    """No anomalies returns None."""
    baseline = AnomalyBaseline(
        kind="prior_attempt",
        sharpe=1.0,
        trial_count=10,
    )
    anomaly = detect_anomalies(
        sharpe=1.1,
        trial_count=10,
        coverage_shrunk=False,
        method_revision_age_days=30,
        baseline=baseline,
    )
    assert anomaly is None


def test_anomaly_detection_with_scorecard_bounds() -> None:
    """Method scorecard bounds baseline works."""
    baseline = AnomalyBaseline(
        kind="method_scorecard_bounds",
        expected_sharpe_range=(0.5, 1.5),
    )
    anomaly = detect_anomalies(
        sharpe=3.0,
        trial_count=5,
        coverage_shrunk=False,
        method_revision_age_days=30,
        baseline=baseline,
    )
    assert anomaly is not None
    assert AnomalyIndicator.SHARPE_OUTLIER in anomaly.indicators


def test_anomaly_presentation_fields() -> None:
    """AnomalyPresentation has expected structure."""
    baseline = AnomalyBaseline(
        kind="prior_attempt",
        sharpe=1.0,
        trial_count=5,
    )
    anomaly = detect_anomalies(
        sharpe=1.0,
        trial_count=5,
        coverage_shrunk=True,
        method_revision_age_days=30,
        baseline=baseline,
    )
    assert anomaly is not None
    assert anomaly.expand_evidence_first is True
    assert anomaly.tone == "checklist"
    assert anomaly.baseline == baseline


def test_anomaly_baseline_kinds() -> None:
    """All baseline kinds are supported."""
    prior_attempt = AnomalyBaseline(
        kind="prior_attempt",
        attempt_id="a-1",
        sharpe=1.5,
        trial_count=8,
    )
    assert prior_attempt.kind == "prior_attempt"
    
    version_1_logic = AnomalyBaseline(
        kind="version_1_logic",
        sharpe=1.0,
        trial_count=5,
    )
    assert version_1_logic.kind == "version_1_logic"
    
    scorecard_bounds = AnomalyBaseline(
        kind="method_scorecard_bounds",
        expected_sharpe_range=(0.5, 2.0),
    )
    assert scorecard_bounds.kind == "method_scorecard_bounds"
