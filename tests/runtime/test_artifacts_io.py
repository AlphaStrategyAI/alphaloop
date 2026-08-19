from __future__ import annotations

import json

import pandas as pd
import yaml

from alphaloop import __version__
from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import GateResult, HardGateName, evidence_to_dict, evaluate_hard_gates
from alphaloop.runtime.artifacts_io import write_candidates_parquet, write_manifest, write_report
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
    assert "signal_mechanism: momentum_12_1" in text
