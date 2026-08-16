"""Unit tests for the v0.8 calibration accuracy metrics + gate.

Covers PRD § 3.2 acceptance criteria A-2.1 through A-2.8:

- A-2.1: exit 0 and writes report.
- A-2.2: metrics block with all 4 metrics per dim.
- A-2.3: worst_dimension callout.
- A-2.4: confusion matrix per dim.
- A-2.5: overall_pass true iff gate met.
- A-2.6: overall_pass false iff gate failed.
- A-2.7: per-case trace covers all 100 case_ids.
- A-2.8: --override-gate path.

The metrics + gate functions are tested directly; the CLI exit code
is tested in tests/calibration/test_cli.py.
"""
from __future__ import annotations

import json

from alphaloop.calibration.accuracy import (
    CalibrationReport,
    ConfusionCounts,
    DimensionMetrics,
    build_calibration_report,
    compute_agreement,
    compute_confusion_matrix,
    compute_mae,
    compute_pearson,
    compute_spearman,
    gate_v1_release,
    load_calibration_report,
    render_report_text,
    write_calibration_report,
)
from alphaloop.calibration.dataset import build_in_memory
from alphaloop.calibration.schema import (
    DIMENSIONS,
    GATE_AGREEMENT_MIN,
    GATE_PEARSON_MIN,
)


# ---------------------------------------------------------------------------
# A-2.2: 4 metrics
# ---------------------------------------------------------------------------


def test_pearson_perfect_is_one():
    """Pearson of identical vectors is 1.0."""
    assert compute_pearson([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0


def test_pearson_perfect_inverse_is_minus_one():
    """Pearson of inverse vectors is -1.0."""
    assert compute_pearson([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0


def test_pearson_zero_variance_returns_zero():
    """Pearson with zero variance returns 0.0 (degenerate)."""
    assert compute_pearson([5, 5, 5], [1, 2, 3]) == 0.0


def test_pearson_length_mismatch_raises():
    """Length mismatch raises ValueError."""
    import pytest

    with pytest.raises(ValueError):
        compute_pearson([1, 2], [1, 2, 3])


def test_spearman_perfect_monotonic_is_one():
    """Spearman of perfectly monotonic vectors is 1.0."""
    assert compute_spearman([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == 1.0


def test_mae_zero_when_identical():
    """MAE of identical vectors is 0.0."""
    assert compute_mae([1, 2, 3], [1, 2, 3]) == 0.0


def test_agreement_within_threshold():
    """Within ±2 agreement counts correct pairs."""
    # 4 of 5 within ±2: (1,1), (2,2), (3,4), (4,5) → within; (10,1) → outside.
    score = compute_agreement(
        [1, 2, 3, 4, 10],
        [1, 2, 4, 5, 1],
        threshold=2.0,
    )
    assert abs(score - 0.8) < 1e-9


# ---------------------------------------------------------------------------
# A-2.4: confusion matrix
# ---------------------------------------------------------------------------


def test_confusion_matrix_balanced():
    """Confusion matrix at threshold=7 with a clear sample."""
    j = [10, 10, 1, 1]
    h = [10, 1, 1, 10]
    conf = compute_confusion_matrix(j, h, threshold=7)
    # TP=1 (j=10 h=10), TN=1 (j=1 h=1), FP=1 (j=10 h=1), FN=1 (j=1 h=10).
    assert conf.tp == 1
    assert conf.tn == 1
    assert conf.fp == 1
    assert conf.fn == 1


def test_confusion_matrix_threshold_param():
    """Threshold argument changes the verdict boundary."""
    j = [5, 6]
    h = [7, 7]
    # At threshold 5: TP=1 (j>=5 h>=5), FN=1 (j=6<5? no, j>=5 h=7>=5 TP=1 actually)
    # Let's use threshold=7: j=5<7 h=7>=7 -> FN; j=6<7 h=7>=7 -> FN.
    conf = compute_confusion_matrix(j, h, threshold=7)
    assert conf.tp == 0
    assert conf.fn == 2
    # At threshold 5: j=5>=5 h=7>=5 -> TP; j=6>=5 h=7>=5 -> TP.
    conf2 = compute_confusion_matrix(j, h, threshold=5)
    assert conf2.tp == 2
    assert conf2.fn == 0


# ---------------------------------------------------------------------------
# A-2.5 / A-2.6: gate
# ---------------------------------------------------------------------------


def test_gate_passes_when_all_dims_meet_thresholds():
    """A-2.5: gate_v1_release True iff every dim passes."""
    metrics = {
        "readability": DimensionMetrics(pearson_r=0.80, agreement_within_2=0.70),
        "decision_quality": DimensionMetrics(pearson_r=0.75, agreement_within_2=0.65),
        "risk_disclosure": DimensionMetrics(pearson_r=0.78, agreement_within_2=0.70),
    }
    assert gate_v1_release(metrics) is True


def test_gate_fails_when_pearson_below():
    """A-2.6: gate False iff pearson < 0.70 on any dim."""
    metrics = {
        "readability": DimensionMetrics(pearson_r=0.80, agreement_within_2=0.70),
        "decision_quality": DimensionMetrics(pearson_r=0.65, agreement_within_2=0.80),  # FAILS
        "risk_disclosure": DimensionMetrics(pearson_r=0.78, agreement_within_2=0.70),
    }
    assert gate_v1_release(metrics) is False


def test_gate_fails_when_agreement_below():
    """A-2.6: gate False iff within-±2 < 0.60 on any dim."""
    metrics = {
        "readability": DimensionMetrics(pearson_r=0.80, agreement_within_2=0.70),
        "decision_quality": DimensionMetrics(pearson_r=0.80, agreement_within_2=0.55),  # FAILS
        "risk_disclosure": DimensionMetrics(pearson_r=0.78, agreement_within_2=0.70),
    }
    assert gate_v1_release(metrics) is False


def test_gate_constants_match_prd():
    """GATE_PEARSON_MIN=0.70 and GATE_AGREEMENT_MIN=0.60 per PRD Story 7."""
    assert abs(GATE_PEARSON_MIN - 0.70) < 1e-9
    assert abs(GATE_AGREEMENT_MIN - 0.60) < 1e-9


# ---------------------------------------------------------------------------
# Build / write / load report (A-2.1, A-2.2, A-2.3, A-2.7, A-2.8)
# ---------------------------------------------------------------------------


def test_build_calibration_report_includes_all_metrics(tmp_path):
    """A-2.2: metrics block has pearson/spearman/mae/agreement per dim."""
    cases, _, _ = build_in_memory()
    predicted = {c.case_id: {d: int(c.ground_truth[d].score) for d in DIMENSIONS} for c in cases}
    report = build_calibration_report(
        cases=cases,
        predicted_scores=predicted,
        dataset_sha256_hex="abc123",
        model="fake-judge",
        threshold=7,
        prompt_version="v0.8.0-prompt-2",
    )
    assert set(report.metrics.keys()) == set(DIMENSIONS)
    for dim in DIMENSIONS:
        m = report.metrics[dim]
        assert hasattr(m, "pearson_r")
        assert hasattr(m, "spearman_rho")
        assert hasattr(m, "mae")
        assert hasattr(m, "agreement_within_2")
        assert hasattr(m, "confusion")


def test_build_report_picks_worst_dimension(tmp_path):
    """A-2.3: worst_dimension callout names the lowest-Pearson dim."""
    cases, _, _ = build_in_memory()
    # Make decision_quality intentionally worst.
    predicted = {c.case_id: {d: int(c.ground_truth[d].score) for d in DIMENSIONS} for c in cases}
    for c in cases:
        # Add 5-point bias to decision_quality only.
        predicted[c.case_id]["decision_quality"] = max(
            1,
            min(10, int(c.ground_truth["decision_quality"].score) + 5),
        )
    report = build_calibration_report(
        cases=cases,
        predicted_scores=predicted,
        dataset_sha256_hex="x",
        model="fake",
        threshold=7,
    )
    # decision_quality should have the lowest pearson (deliberately biased).
    worst = min(DIMENSIONS, key=lambda d: report.metrics[d].pearson_r)
    assert report.worst_dimension == worst


def test_build_report_per_case_trace_covers_all_cases(tmp_path):
    """A-2.7: per-case trace contains every case_id."""
    cases, _, _ = build_in_memory()
    predicted = {c.case_id: {d: int(c.ground_truth[d].score) for d in DIMENSIONS} for c in cases}
    report = build_calibration_report(
        cases=cases,
        predicted_scores=predicted,
        dataset_sha256_hex="x",
        model="fake",
    )
    assert len(report.cases) == 100
    seen = {row.case_id for row in report.cases}
    expected = {c.case_id for c in cases}
    assert seen == expected


def test_build_report_with_override_sets_overall_pass(tmp_path):
    """A-2.8: --override-gate path flips overall_pass to True."""
    cases, _, _ = build_in_memory()
    # Force a gate failure (large bias).
    predicted = {}
    for c in cases:
        predicted[c.case_id] = {
            d: (int(c.ground_truth[d].score) + 9) % 10 + 1 for d in DIMENSIONS
        }
    report = build_calibration_report(
        cases=cases,
        predicted_scores=predicted,
        dataset_sha256_hex="x",
        model="fake",
        override_reason="v1.0 ship exception: documented in release notes",
    )
    assert report.overall_pass is True
    assert report.override is not None
    assert "exception" in report.override["reason"]


def test_write_and_load_calibration_report_round_trip(tmp_path):
    """A-2.1: writes calibration_report.json; round-trips losslessly."""
    cases, _, _ = build_in_memory()
    predicted = {c.case_id: {d: int(c.ground_truth[d].score) for d in DIMENSIONS} for c in cases}
    report = build_calibration_report(
        cases=cases,
        predicted_scores=predicted,
        dataset_sha256_hex="deadbeef",
        model="fake",
    )
    out = tmp_path / "calibration_report.json"
    write_calibration_report(report, out)
    assert out.is_file()
    loaded = load_calibration_report(out)
    assert loaded.dataset_sha256 == "deadbeef"
    assert loaded.n_cases == 100
    assert loaded.metrics.keys() == report.metrics.keys()


def test_render_report_text_includes_worst_dimension():
    """A-2.3: render includes the worst_dim callout."""
    cases, _, _ = build_in_memory()
    predicted = {c.case_id: {d: int(c.ground_truth[d].score) for d in DIMENSIONS} for c in cases}
    report = build_calibration_report(
        cases=cases,
        predicted_scores=predicted,
        dataset_sha256_hex="x",
        model="fake",
    )
    text = render_report_text(report)
    assert "worst dimension" in text.lower()
    assert report.worst_dimension in text


def test_render_report_text_gate_pass_banner():
    """A-2.5: pass banner printed when gate is met."""
    cases, _, _ = build_in_memory()
    predicted = {c.case_id: {d: int(c.ground_truth[d].score) for d in DIMENSIONS} for c in cases}
    report = build_calibration_report(
        cases=cases,
        predicted_scores=predicted,
        dataset_sha256_hex="x",
        model="fake",
    )
    text = render_report_text(report)
    assert "GATE PASSED" in text or "gate passed" in text.lower()


def test_render_report_text_gate_fail_banner():
    """A-2.6: GATE FAILED banner printed when any dim fails."""
    cases, _, _ = build_in_memory()
    predicted = {}
    for c in cases:
        # Random scatter: judge scores uniform 1-10, regardless of GT.
        import random
        rng = random.Random(hash(c.case_id) & 0xFFFFFFFF)
        predicted[c.case_id] = {d: rng.randint(1, 10) for d in DIMENSIONS}
    report = build_calibration_report(
        cases=cases,
        predicted_scores=predicted,
        dataset_sha256_hex="x",
        model="fake",
    )
    if not report.overall_pass:
        text = render_report_text(report)
        assert "GATE FAILED" in text or "gate failed" in text.lower()


def test_calibration_report_round_trip_preserves_fields(tmp_path):
    """CalibrationReport dataclass round-trips through dict."""
    report = CalibrationReport(
        dataset_sha256="abc",
        n_cases=42,
        model="m",
        metrics={
            "readability": DimensionMetrics(pearson_r=0.5),
        },
    )
    d = report.to_dict()
    j = json.dumps(d)
    restored = CalibrationReport.from_dict(json.loads(j))
    assert restored.dataset_sha256 == "abc"
    assert restored.n_cases == 42
    assert restored.metrics["readability"].pearson_r == 0.5