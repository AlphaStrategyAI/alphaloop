from __future__ import annotations

import json

import pandas as pd
import yaml

from alphaloop import __version__
from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import GateResult, HardGateName, evidence_to_dict, evaluate_hard_gates
from alphaloop.runtime.artifacts_io import (
    format_gate_line,
    format_primary_evidence,
    write_candidates_parquet,
    write_manifest,
    write_report,
)
from tests.runtime.test_supervisor import _spec


def test_manifest_records_engine_seed_and_null_dataset(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    spec = _spec()
    write_manifest(layout, spec, engine_version=__version__)
    payload = yaml.safe_load(layout.manifest.read_text(encoding="utf-8"))
    assert payload["engine_version"] == "0.5.0"
    assert payload["seed"] == spec.seed
    assert payload["spec_id"] == spec.spec_id
    assert payload["dataset_id"] is None
    assert payload["dataset_sha256"] is None
    assert payload["time_budget_s"] == spec.time_budget_s
    assert payload["cost_budget_usd"] == spec.cost_budget_usd


def test_candidates_parquet_mirrors_ledger(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    layout.trial_ledger.write_text(
        json.dumps({"trial_id": "c_1", "kind": "rsi", "parameters": {"window": 21}, "revision": "method"})
        + "\n",
        encoding="utf-8",
    )
    write_candidates_parquet(layout)
    frame = pd.read_parquet(layout.candidates)
    assert list(frame["trial_id"]) == ["c_1"]
    assert list(frame["kind"]) == ["rsi"]


def test_report_is_a_view_of_sealed_evidence(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    evidence = evaluate_hard_gates(
        (HardGateName.DSR,),
        (GateResult(name=HardGateName.DSR, passed=True, detail={}),),
    )
    layout.evidence.mkdir()
    (layout.evidence / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    write_report(layout, research_outcome="FOUND", stop_reason="all_gates_passed")
    text = layout.report.read_text(encoding="utf-8")
    assert "# Research conclusion" in text
    assert "This report does not claim alpha or future profitability." in text
    assert "FOUND" in text
    assert "all_gates_passed" in text
    assert "dsr" in text.lower()


def test_report_includes_elimination_funnel(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    evidence = evaluate_hard_gates(
        (HardGateName.DSR,),
        (GateResult(name=HardGateName.DSR, passed=False, detail={}),),
    )
    trials = layout.evidence / "trials"
    trials.mkdir(parents=True)
    body = json.dumps(evidence_to_dict(evidence))
    (layout.evidence / "gates.json").write_text(body)
    (trials / "c_1.json").write_text(body)
    layout.trial_ledger.write_text(
        json.dumps({"trial_id": "c_1", "revision": "none"}) + "\n",
        encoding="utf-8",
    )
    write_report(layout, research_outcome="NO_EVIDENCE", stop_reason="hard_gate_failed")
    text = layout.report.read_text(encoding="utf-8")
    assert "primary_evidence: dsr — Deflated Sharpe Ratio failed" in text
    assert "## Elimination funnel" in text
    assert "evaluated: 1" in text
    assert "failed: 1" in text
    assert "dsr — Deflated Sharpe Ratio: 1" in text
    assert "dsr: 1\n" not in text
    assert "## Qualifying candidates" in text
    assert "none" in text


def test_report_includes_frozen_hypothesis_and_n_trials(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    spec = _spec()
    layout.trial_ledger.write_text(
        json.dumps({"trial_id": "c_1", "revision": "none"})
        + "\n"
        + json.dumps({"trial_id": "c_1", "revision": "method"})
        + "\n"
        + json.dumps({"trial_id": "c_2", "revision": "none"})
        + "\n",
        encoding="utf-8",
    )
    write_report(
        layout,
        research_outcome="NO_EVIDENCE",
        stop_reason="hard_gate_failed",
        spec=spec,
    )
    text = layout.report.read_text(encoding="utf-8")
    assert "This report does not claim alpha or future profitability." in text
    assert f"spec_id: {spec.spec_id}" in text
    assert f"seed: {spec.seed}" in text
    assert "n_trials: 2" in text
    assert spec.hypothesis.statement in text
    assert "signal_mechanism: momentum_12_1 — 12-1 momentum" in text
    assert "signal_mechanism: momentum_12_1\n" not in text
    assert (
        "market_profile: us-equity-daily — US equities, NYSE, 5 bps, default SPY"
        in text
    )
    assert "market_profile: us-equity-daily\n" not in text


def test_report_includes_walk_forward_detail_keys(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    evidence = evaluate_hard_gates(
        (HardGateName.WALK_FORWARD,),
        (
            GateResult(
                name=HardGateName.WALK_FORWARD,
                passed=False,
                detail={
                    "regime_stable": False,
                    "returns_scope": "oos_walk_forward",
                    "oos_sharpe_median": -0.2,
                },
            ),
        ),
    )
    layout.evidence.mkdir()
    (layout.evidence / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    write_report(layout, research_outcome="NO_EVIDENCE", stop_reason="hard_gate_failed")
    text = layout.report.read_text(encoding="utf-8")
    assert "walk_forward — walk-forward OOS: fail" in text
    assert "regime_stable=false" in text
    assert "returns_scope=oos_walk_forward" in text
    assert "oos_sharpe_median=-0.2" in text


def test_format_primary_evidence_follows_sealed_outcome():
    failed = {"required": ["dsr"], "results": [{"name": "dsr", "passed": False, "detail": {}}]}
    assert (
        format_primary_evidence("FOUND", evidence=failed, dominant_failures=("dsr",))
        == "all required hard gates passed"
    )
    assert (
        format_primary_evidence(
            "NO_EVIDENCE", evidence=failed, dominant_failures=("dsr", "walk_forward")
        )
        == "dsr — Deflated Sharpe Ratio failed"
    )
    assert (
        format_primary_evidence("NO_EVIDENCE", evidence=failed, dominant_failures=())
        == "a required hard gate failed"
    )
    assert (
        format_primary_evidence("INCONCLUSIVE", evidence=None, dominant_failures=())
        == "no sealed gates.json"
    )
    assert (
        format_primary_evidence(
            "INCONCLUSIVE",
            evidence={
                "required": ["dsr", "walk_forward"],
                "results": [{"name": "dsr", "passed": True, "detail": {}}],
            },
            dominant_failures=(),
        )
        == "missing walk_forward — walk-forward OOS"
    )
    assert (
        format_primary_evidence(
            "INCONCLUSIVE",
            evidence={"required": ["dsr"], "results": [{"name": "dsr", "passed": True, "detail": {}}]},
            dominant_failures=(),
        )
        == "incomplete evidence set"
    )
    assert format_primary_evidence("NONE", evidence=None, dominant_failures=()) is None


def test_format_gate_line_uses_hard_gate_gloss():
    assert (
        format_gate_line({"name": "dsr", "passed": True, "detail": {}})
        == "dsr — Deflated Sharpe Ratio: pass"
    )
    assert format_gate_line({"name": "custom", "passed": True, "detail": {}}) == "custom: pass"


def test_format_primary_evidence_glosses_gate_names():
    failed = {"required": ["dsr"], "results": [{"name": "dsr", "passed": False, "detail": {}}]}
    assert (
        format_primary_evidence(
            "NO_EVIDENCE", evidence=failed, dominant_failures=("dsr",)
        )
        == "dsr — Deflated Sharpe Ratio failed"
    )
    assert (
        format_primary_evidence(
            "INCONCLUSIVE",
            evidence={
                "required": ["dsr", "walk_forward"],
                "results": [{"name": "dsr", "passed": True, "detail": {}}],
            },
            dominant_failures=(),
        )
        == "missing walk_forward — walk-forward OOS"
    )


def test_format_gate_line_empty_detail():
    assert format_gate_line({"name": "dsr", "passed": True, "detail": {}}) == "dsr — Deflated Sharpe Ratio: pass"


def test_format_gate_line_walk_forward_order_and_bools():
    line = format_gate_line(
        {
            "name": "walk_forward",
            "passed": False,
            "detail": {
                "regime_stable": False,
                "oos_sharpe_median": 0.1234567,
                "first_half_sharpe": 1.0,
                "second_half_sharpe": -0.5,
                "returns_scope": "oos_walk_forward",
                "oos_sharpe_mean": 0.25,
                "ignored": "nope",
            },
        }
    )
    assert line.startswith("walk_forward — walk-forward OOS: fail · ")
    assert "ignored=" not in line
    assert line == (
        "walk_forward — walk-forward OOS: fail · returns_scope=oos_walk_forward · "
        "oos_sharpe_mean=0.25 · oos_sharpe_median=0.123457 · "
        "first_half_sharpe=1 · second_half_sharpe=-0.5 · regime_stable=false"
    )


def test_format_gate_line_dsr_n_trials():
    line = format_gate_line(
        {
            "name": "dsr",
            "passed": True,
            "detail": {"n_trials": 3, "dsr": 0.9, "returns_scope": "oos_walk_forward"},
        }
    )
    assert line == (
        "dsr — Deflated Sharpe Ratio: pass · returns_scope=oos_walk_forward · n_trials=3 · dsr=0.9"
    )


def test_format_gate_line_includes_pbo_when_present():
    line = format_gate_line(
        {
            "name": "dsr",
            "passed": False,
            "detail": {
                "dsr": 0.9,
                "pbo": 0.8,
                "pbo_n_strategies": 3,
                "pbo_n_paths": 20,
                "pbo_n_groups": 6,
                "pbo_passes": False,
            },
        }
    )
    assert "pbo=0.8" in line
    assert "pbo_n_strategies=3" in line
    assert "pbo_n_paths=20" in line
    assert "pbo_n_groups=6" in line
    assert "pbo_passes=false" in line
