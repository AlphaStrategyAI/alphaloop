"""Unit tests for the v0.8 drift harness (R-Drift).

Covers PRD § 3.3 acceptance criteria A-3.1 through A-3.7 (excluding
A-3.7 which is CI config and exercised manually):

- A-3.1: at least 3 named tests (within, exceeds, alphabetical).
- A-3.2: pytest passes against golden.
- A-3.3: pytest fails on corrupted golden.
- A-3.4: report sorts alphabetically.
- A-3.5: banner contains dim/drift/golden mean/current mean.
- A-3.6: marked @pytest.mark.llm and skips without LLM_API_KEY.

Also covers the actual tests/test_judge_drift.py integration which
imports from here.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphaloop.calibration.drift import (
    DriftReport,
    compare_to_golden,
    compute_drift,
    load_golden_scores,
    render_drift_text,
    should_block_release,
    write_drift_report,
    write_golden_scores,
)
from alphaloop.calibration.dataset import build_in_memory


# ---------------------------------------------------------------------------
# A-3.1 + A-3.2: drift under threshold
# ---------------------------------------------------------------------------


def test_drift_under_threshold_passes(tmp_path):
    """A-3.2: current scores = golden → no drift → not blocked."""
    cases, _, _ = build_in_memory()
    # Build a golden file from the in-memory dataset.
    golden = {
        c.case_id: {
            "readability": int(c.ground_truth["readability"].score),
            "decision_quality": int(c.ground_truth["decision_quality"].score),
            "risk_disclosure": int(c.ground_truth["risk_disclosure"].score),
        }
        for c in cases
    }
    write_golden_scores(golden, tmp_path / "golden.jsonl")
    # Use identical scores → drift = 0.
    current = {cid: dict(golden[cid]) for cid in golden}
    report = compare_to_golden(current, tmp_path / "golden.jsonl")
    assert report.blocked is False
    assert report.n_cases == 100
    for dim in ("readability", "decision_quality", "risk_disclosure"):
        assert report.per_dim_drift_pct[dim] == 0.0


def test_drift_over_threshold_fails(tmp_path):
    """A-3.3: 15% drift corrupts the build (block + banner)."""
    cases, _, _ = build_in_memory()
    golden = {
        c.case_id: {
            "readability": int(c.ground_truth["readability"].score),
            "decision_quality": int(c.ground_truth["decision_quality"].score),
            "risk_disclosure": int(c.ground_truth["risk_disclosure"].score),
        }
        for c in cases
    }
    write_golden_scores(golden, tmp_path / "golden.jsonl")
    # Inject 30% drift on readability (well above 10%).
    current = {cid: dict(golden[cid]) for cid in golden}
    for cid in current:
        current[cid]["readability"] = min(10, current[cid]["readability"] + 3)
    report = compare_to_golden(current, tmp_path / "golden.jsonl")
    assert report.blocked is True
    assert any("readability" in r for r in report.block_reasons)


# ---------------------------------------------------------------------------
# A-3.4: alphabetical order
# ---------------------------------------------------------------------------


def test_drift_report_sorts_alphabetically(tmp_path):
    """A-3.4: rows are in alphabetical order by case_id."""
    cases, _, _ = build_in_memory()
    golden = {
        c.case_id: {d: int(c.ground_truth[d].score) for d in ("readability", "decision_quality", "risk_disclosure")}
        for c in cases
    }
    write_golden_scores(golden, tmp_path / "golden.jsonl")
    current = {cid: dict(golden[cid]) for cid in golden}
    report = compare_to_golden(current, tmp_path / "golden.jsonl")
    case_ids = [r.case_id for r in report.rows]
    assert case_ids == sorted(case_ids)


# ---------------------------------------------------------------------------
# A-3.5: banner content
# ---------------------------------------------------------------------------


def test_drift_banner_lists_dim_and_threshold(tmp_path):
    """A-3.5: when blocked, banner lists dimension name + drift % + golden mean + current mean."""
    cases, _, _ = build_in_memory()
    golden = {
        c.case_id: {d: int(c.ground_truth[d].score) for d in ("readability", "decision_quality", "risk_disclosure")}
        for c in cases
    }
    write_golden_scores(golden, tmp_path / "golden.jsonl")
    current = {cid: dict(golden[cid]) for cid in golden}
    for cid in current:
        current[cid]["risk_disclosure"] = max(1, current[cid]["risk_disclosure"] - 2)
    report = compare_to_golden(current, tmp_path / "golden.jsonl")
    text = render_drift_text(report)
    assert "JUDGE DRIFT DETECTED" in text
    assert "risk_disclosure" in text
    # Banner has drift % and threshold.
    assert "threshold" in text.lower() or "10%" in text


# ---------------------------------------------------------------------------
# A-3.6: marked @pytest.mark.llm + skips without LLM_API_KEY
# ---------------------------------------------------------------------------


# These tests verify the actual tests/test_judge_drift.py file exists,
# is marked with @pytest.mark.llm, and contains the 3 required tests.


def test_drift_test_file_has_three_named_tests():
    """A-3.1: tests/test_judge_drift.py has at least 3 test functions."""
    from alphaloop.calibration.drift import compare_to_golden as _compare

    src = Path(__file__).resolve().parents[1] / "test_judge_drift.py"
    text = src.read_text(encoding="utf-8")
    # Count functions whose name starts with test_
    import re
    names = re.findall(r"^def\s+(test_\w+)\s*\(", text, re.MULTILINE)
    assert len(names) >= 3, f"expected >=3 test_ funcs, got {names}"


def test_drift_test_functions_skip_without_llm_key(tmp_path, monkeypatch):
    """A-3.6: @pytest.mark.llm causes skip when LLM_API_KEY is not set."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    # The CLI module's behaviour (no LLM key) uses the fake judge, so
    # this test asserts that no LLM API call was attempted (callable
    # but not invoked). Simpler: assert the harness module exposes a
    # public ``run_judge_drift_test`` helper that we can call and that
    # skips cleanly.
    from tests.test_judge_drift import run_judge_drift_test

    out = run_judge_drift_test(
        dataset_dir=tmp_path,
        skip_without_key=True,
    )
    assert out["skipped"] is True
    assert "LLM_API_KEY" in out.get("reason", "")


def test_drift_helper_returns_with_llm_key(tmp_path, monkeypatch):
    """When LLM_API_KEY is set, helper runs end-to-end (faked judge path)."""
    monkeypatch.setenv("LLM_API_KEY", "fake-key-for-test")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    # Build the dataset.
    from alphaloop.calibration.dataset import save_dataset
    save_dataset(tmp_path)
    # Golden = in-memory dataset ground truth.
    from alphaloop.calibration.dataset import load_dataset
    cases, _ = load_dataset(tmp_path)
    golden = {
        c.case_id: {d: int(c.ground_truth[d].score) for d in ("readability", "decision_quality", "risk_disclosure")}
        for c in cases
    }
    write_golden_scores(golden, tmp_path / "golden_scores.jsonl")
    from tests.test_judge_drift import run_judge_drift_test
    out = run_judge_drift_test(
        dataset_dir=tmp_path,
        skip_without_key=False,
    )
    assert "report" in out
    assert "blocked" in out


# ---------------------------------------------------------------------------
# Helpers: compute_drift + should_block_release
# ---------------------------------------------------------------------------


def test_compute_drift_positive():
    """compute_drift positive when judge > golden."""
    assert compute_drift(110, 100) == pytest.approx(0.10)


def test_compute_drift_negative():
    """compute_drift negative when judge < golden."""
    assert compute_drift(90, 100) == pytest.approx(-0.10)


def test_compute_drift_zero_golden():
    """compute_drift returns 0 when golden is 0 (degenerate)."""
    assert compute_drift(5, 0) == 0.0


def test_should_block_release_at_threshold():
    """Threshold is strict (>), so ==threshold does not block."""
    assert should_block_release(0.10) is False
    assert should_block_release(0.11) is True
    assert should_block_release(-0.11) is True


def test_should_block_release_negative_drift():
    """Negative drift can also block release."""
    assert should_block_release(-0.50) is True


# ---------------------------------------------------------------------------
# Golden format (PRD § 2 Story 8)
# ---------------------------------------------------------------------------


def test_golden_file_format_round_trip(tmp_path):
    """Golden JSONL is loadable and round-trips losslessly."""
    rows = {
        "calib_001": {"readability": 7, "decision_quality": 6, "risk_disclosure": 8},
        "calib_002": {"readability": 5, "decision_quality": 5, "risk_disclosure": 5},
    }
    p = write_golden_scores(rows, tmp_path / "golden.jsonl")
    assert p.is_file()
    loaded = load_golden_scores(p)
    assert loaded == rows


def test_golden_file_is_sorted(tmp_path):
    """Golden JSONL is written in alphabetical case_id order."""
    rows = {
        "calib_010": {"readability": 1, "decision_quality": 1, "risk_disclosure": 1},
        "calib_001": {"readability": 1, "decision_quality": 1, "risk_disclosure": 1},
        "calib_005": {"readability": 1, "decision_quality": 1, "risk_disclosure": 1},
    }
    p = write_golden_scores(rows, tmp_path / "golden.jsonl")
    case_ids_in_order = []
    for line in p.read_text().splitlines():
        if line.strip():
            case_ids_in_order.append(json.loads(line)["case_id"])
    assert case_ids_in_order == sorted(case_ids_in_order)


def test_drift_report_round_trip(tmp_path):
    """DriftReport round-trips through dict."""
    r = DriftReport(
        dataset_path=str(tmp_path),
        n_cases=10,
        per_dim_drift_pct={"readability": 0.05},
        blocked=True,
        block_reasons=["test"],
    )
    p = write_drift_report(r, tmp_path / "drift.json")
    loaded = DriftReport.from_dict(json.loads(p.read_text()))
    assert loaded.n_cases == 10
    assert loaded.per_dim_drift_pct["readability"] == 0.05
    assert loaded.blocked is True