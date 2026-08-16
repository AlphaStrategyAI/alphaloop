"""Integration tests for the ``alphaloop judge --calibration`` CLI.

Covers PRD § 3.2 acceptance criteria A-2.1 through A-2.8 from the
CLI perspective:

- A-2.1: exit 0 and writes report.
- A-2.2..A-2.6: the report content / shape.
- A-2.7: cases[] covers all 100 case_ids.
- A-2.8: --override-gate.

Plus a smoke test that runs ``alphaloop judge --calibration`` in a
subprocess to verify the CLI is wired into the main dispatcher.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from alphaloop.calibration.cli import (
    DEFAULT_DATASET_DIR,
    cmd_judge_calibrate_prompt,
    cmd_judge_calibration,
)
from alphaloop.calibration.dataset import save_dataset
from alphaloop.calibration.schema import DIMENSIONS


def _make_args(**kwargs):
    """Build a minimal argparse.Namespace mirroring the CLI."""
    import argparse

    base = dict(
        calibration=False,
        calibrate_prompt=False,
        dataset=None,
        output=None,
        threshold=7,
        judge_model=None,
        judge_prompt_version=None,
        override_gate=False,
        reason=None,
        freeze_golden=False,
        dry_run=False,
        prompt_a="v0.6.0-prompt-1",
        prompt_b="v0.8.0-prompt-2",
    )
    base.update(kwargs)
    return argparse.Namespace(**base)


# ---------------------------------------------------------------------------
# A-2.1: exit 0 + writes report
# ---------------------------------------------------------------------------


def test_cmd_judge_calibration_exits_zero_and_writes(tmp_path):
    """A-2.1: CLI exits 0 and writes calibration_report.json."""
    save_dataset(tmp_path / "v1")
    args = _make_args(
        calibration=True,
        dataset=str(tmp_path / "v1"),
        output=str(tmp_path / "calibration_report.json"),
    )
    rc = cmd_judge_calibration(args)
    assert rc == 0
    assert (tmp_path / "calibration_report.json").is_file()


def test_cmd_judge_calibration_uses_default_dataset_when_missing(tmp_path, monkeypatch):
    """When no dataset on disk, the CLI builds in-memory and exits 0."""
    # We use a non-existent path; the CLI falls back to in-memory.
    args = _make_args(
        calibration=True,
        dataset=str(tmp_path / "does-not-exist"),
        output=str(tmp_path / "calibration_report.json"),
    )
    rc = cmd_judge_calibration(args)
    assert rc == 0
    assert (tmp_path / "calibration_report.json").is_file()


# ---------------------------------------------------------------------------
# A-2.2 / A-2.5 / A-2.6: report content
# ---------------------------------------------------------------------------


def test_calibration_report_has_all_dim_metrics(tmp_path):
    """A-2.2: metrics block contains 4 metrics per dim."""
    save_dataset(tmp_path / "v1")
    args = _make_args(
        calibration=True,
        dataset=str(tmp_path / "v1"),
        output=str(tmp_path / "report.json"),
    )
    cmd_judge_calibration(args)
    report = json.loads((tmp_path / "report.json").read_text())
    for dim in DIMENSIONS:
        m = report["metrics"][dim]
        assert "pearson_r" in m
        assert "spearman_rho" in m
        assert "mae" in m
        assert "agreement_within_2" in m


def test_calibration_report_has_worst_dimension_callout(tmp_path):
    """A-2.3: worst_dimension callout is included."""
    save_dataset(tmp_path / "v1")
    args = _make_args(
        calibration=True,
        dataset=str(tmp_path / "v1"),
        output=str(tmp_path / "report.json"),
    )
    cmd_judge_calibration(args)
    report = json.loads((tmp_path / "report.json").read_text())
    assert "worst_dimension" in report
    assert "worst_dimension_metric" in report


def test_calibration_report_has_confusion_breakdown(tmp_path):
    """A-2.4: confusion-style breakdown per dim at threshold=7."""
    save_dataset(tmp_path / "v1")
    args = _make_args(
        calibration=True,
        dataset=str(tmp_path / "v1"),
        output=str(tmp_path / "report.json"),
    )
    cmd_judge_calibration(args)
    report = json.loads((tmp_path / "report.json").read_text())
    for dim in DIMENSIONS:
        conf = report["metrics"][dim]["confusion"]
        assert "tp" in conf
        assert "tn" in conf
        assert "fp" in conf
        assert "fn" in conf


def test_calibration_report_overall_pass_true_when_perfect(tmp_path):
    """A-2.5: with perfect agreement, overall_pass=True, exit 0."""
    save_dataset(tmp_path / "v1")
    args = _make_args(
        calibration=True,
        dataset=str(tmp_path / "v1"),
        output=str(tmp_path / "report.json"),
    )
    rc = cmd_judge_calibration(args)
    report = json.loads((tmp_path / "report.json").read_text())
    # Fake judge = ground truth → perfect agreement.
    assert report["overall_pass"] is True
    assert rc == 0


# ---------------------------------------------------------------------------
# A-2.7: per-case trace
# ---------------------------------------------------------------------------


def test_calibration_report_cases_cover_all_100(tmp_path):
    """A-2.7: cases[] contains all 100 case_ids."""
    save_dataset(tmp_path / "v1")
    args = _make_args(
        calibration=True,
        dataset=str(tmp_path / "v1"),
        output=str(tmp_path / "report.json"),
    )
    cmd_judge_calibration(args)
    report = json.loads((tmp_path / "report.json").read_text())
    assert len(report["cases"]) == 100
    seen = {c["case_id"] for c in report["cases"]}
    assert len(seen) == 100


# ---------------------------------------------------------------------------
# A-2.8: --override-gate
# ---------------------------------------------------------------------------


def test_calibration_with_override_gate_exits_zero(tmp_path):
    """A-2.8: --override-gate records reason and exits 0."""
    save_dataset(tmp_path / "v1")
    args = _make_args(
        calibration=True,
        dataset=str(tmp_path / "v1"),
        output=str(tmp_path / "report.json"),
        override_gate=True,
        reason="documented ship exception for v1.0",
    )
    rc = cmd_judge_calibration(args)
    assert rc == 0
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["override"] is not None
    assert "documented ship exception" in report["override"]["reason"]


# ---------------------------------------------------------------------------
# A-2.1 (CLI smoke): subprocess invocation
# ---------------------------------------------------------------------------


def test_judge_calibration_subprocess(tmp_path):
    """Subprocess smoke test: 'alphaloop judge --calibration' runs end-to-end."""
    save_dataset(tmp_path / "v1")
    repo = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo / "src")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "alphaloop.cli.main",
            "judge",
            "--calibration",
            "--dataset",
            str(tmp_path / "v1"),
            "--output",
            str(tmp_path / "report.json"),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    assert (tmp_path / "report.json").is_file()


def test_judge_calibrate_prompt_subprocess(tmp_path):
    """Subprocess smoke test for --calibrate-prompt."""
    save_dataset(tmp_path / "v1")
    repo = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo / "src")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "alphaloop.cli.main",
            "judge",
            "--calibrate-prompt",
            "--dataset",
            str(tmp_path / "v1"),
            "--output",
            str(tmp_path / "ab.json"),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    assert (tmp_path / "ab.json").is_file()
    ab = json.loads((tmp_path / "ab.json").read_text())
    assert ab["version_a"] == "v0.6.0-prompt-1"
    assert ab["version_b"] == "v0.8.0-prompt-2"


def test_judge_help_does_not_crash():
    """alphaloop judge --help exits 0 with usage text."""
    repo = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo / "src")
    proc = subprocess.run(
        [sys.executable, "-m", "alphaloop.cli.main", "judge", "--help"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 0
    assert "calibration" in proc.stdout.lower() or "calibrate-prompt" in proc.stdout.lower()