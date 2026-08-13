"""
Tests for the `alphaloop report` CLI.

The CLI is the user-facing entry point for the v1.0 acceptance
report. We test:
  - The CLI is registered
  - Help text is informative
  - Running the report produces a valid Markdown file
  - All 6 acceptance questions appear in the output
  - The summary line reflects actual pass/fail
  - Custom --seed produces deterministic output
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _alphaloop_python() -> str:
    """Return the python interpreter that has alphaloop installed.

    `alphaloop` is a pip-installed console script whose target is
    `alphaloop.cli:main`. When pytest is run from a different
    environment than the one where alphaloop was installed, the
    `alphaloop` binary may not be on PATH. To be robust we use
    `sys.executable` (the same interpreter running pytest) and
    invoke the CLI as a module.
    """
    return sys.executable


def _run_report(*args: str) -> subprocess.CompletedProcess:
    """Invoke `alphaloop report ...` via the installed entry point."""
    py = _alphaloop_python()
    return subprocess.run(
        [py, "-c",
         "import sys; from alphaloop.cli import main; sys.exit(main(sys.argv[1:]))",
         "report", *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=60,
    )


def test_alphaloop_cli_exists():
    """The `alphaloop` CLI's `main` function should be importable."""
    py = _alphaloop_python()
    r = subprocess.run(
        [py, "-c",
         "import sys; from alphaloop.cli import main; "
         "sys.argv = ['alphaloop', '--help']; "
         "main()"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=10,
    )
    assert r.returncode == 0
    # The help text should mention at least one subcommand
    out = r.stdout.lower()
    assert "backtest" in out or "report" in out or "usage" in out


def test_report_help():
    r = _run_report("--help")
    assert r.returncode == 0
    assert "--output" in r.stdout
    assert "--seed" in r.stdout


def test_report_runs_and_prints_to_stdout():
    r = _run_report("--seed", "0")
    assert r.returncode == 0
    out = r.stdout
    assert "# alphaloop v1.0 Acceptance Report" in out
    # All 6 questions should appear
    for q in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]:
        assert q in out, f"Missing question {q} in report output"
    # Summary section
    assert "Acceptance questions passed" in out


def test_report_writes_to_output_file(tmp_path):
    out_file = tmp_path / "report.md"
    r = _run_report("--output", str(out_file), "--seed", "0")
    assert r.returncode == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "alphaloop v1.0 Acceptance Report" in content
    assert "Q1" in content and "Q6" in content
    assert "Alpha factor library" in content


def test_report_alpha_factor_table_present():
    """The 10-factor comparison table should appear in the report."""
    r = _run_report("--seed", "0")
    out = r.stdout
    # At least one factor name should be in the table
    for factor in ["rsi", "macd", "bollinger_zscore", "obv_slope"]:
        assert factor in out, f"Factor {factor} missing from report"


def test_report_summary_is_honest():
    """The summary line should report a number, not gloss over failures."""
    r = _run_report("--seed", "0")
    out = r.stdout
    # The summary must mention a fraction like "X/6" — never just say "all pass"
    assert re.search(r"\d+/6 questions passed", out)
    # The honest disclosure is at the bottom
    assert "honest" in out.lower() or "failing" in out.lower()


def test_report_deterministic_with_same_seed():
    """Same seed should produce identical reports (modulo timestamp)."""
    r1 = _run_report("--seed", "42")
    r2 = _run_report("--seed", "42")
    # Strip the _Generated: ..._ timestamp line which varies by second.
    ts_re = re.compile(r"_Generated: .*?_")
    out1 = ts_re.sub("", r1.stdout)
    out2 = ts_re.sub("", r2.stdout)
    assert out1 == out2


def test_report_different_with_different_seed():
    """Different seeds should produce at least some differences."""
    r1 = _run_report("--seed", "0")
    r2 = _run_report("--seed", "123")
    assert r1.stdout != r2.stdout


def test_report_contains_pass_and_fail_markers():
    """The report should explicitly use PASS/FAIL markers."""
    r = _run_report("--seed", "0")
    out = r.stdout
    assert "PASS" in out
    assert "FAIL" in out  # At least one fail on random walk


def test_report_parkinson_excluded():
    """Parkinson vol is a feature, not a signal — should NOT be in the
    alpha comparison table."""
    r = _run_report("--seed", "0")
    # The alpha factor table should NOT list parkinson
    out = r.stdout
    table_match = re.search(
        r"## Alpha factor library.*?(## Summary|\Z)", out, re.DOTALL
    )
    assert table_match is not None
    table_section = table_match.group(0)
    # parkinson should not appear in the table
    assert "parkinson" not in table_section.lower()