from __future__ import annotations

import json
import zipfile

import pytest

from alphaloop.cli.main import create_parser, main
from alphaloop.runtime.morning import EXPORT_NO_ALPHA
from alphaloop.contracts.gates import (
    GateResult,
    HardGateName,
    evidence_to_dict,
    evaluate_hard_gates,
)
from alphaloop.runtime.store import JobStore
from tests.runtime.test_supervisor import _spec


def _found_job(tmp_path, candidate_id: str = "c1"):
    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    job = store.create(_spec())
    required = tuple(HardGateName(name) for name in job.spec.success_criteria.hard_gates)
    evidence = evaluate_hard_gates(
        required,
        tuple(GateResult(name=name, passed=True, detail={}) for name in required),
    )
    evidence_dir = tmp_path / job.run_id / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    (tmp_path / job.run_id / "trial-ledger.jsonl").write_text(
        json.dumps(
            {
                "trial_id": candidate_id,
                "kind": "momentum_12_1",
                "parameters": {},
                "revision": "none",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    store.complete_from_artifacts(job.run_id)
    return store.get(job.run_id)


def test_export_help_describes_asb_bundle():
    parser = create_parser()
    command_action = next(
        action for action in parser._actions if action.dest == "command"
    )
    export_help = next(
        choice.help
        for choice in command_action._choices_actions
        if choice.dest == "export"
    )
    assert "placeholder" not in export_help.lower()
    assert ".asb" in export_help.lower()


def test_export_writes_asb_zip(tmp_path, capsys):
    job = _found_job(tmp_path)
    out = tmp_path / "strategy.asb"
    rc = main(
        [
            "export",
            "c1",
            "--run-id",
            job.run_id,
            "--data-dir",
            str(tmp_path),
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    assert zipfile.is_zipfile(out)
    with zipfile.ZipFile(out) as archive:
        names = archive.namelist()
    assert "bundle.yaml" in names
    assert "strategy.dsl.yaml" in names
    assert "evidence/gates.json" in names
    assert "conformance/expected_weights.yaml" in names
    assert not any(name.endswith(".py") for name in names)
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert lines[0] == "FOUND"
    assert lines[1] == "Qualifying: c1"
    assert lines[2] == f"Exported: {out}"
    assert lines[3] == EXPORT_NO_ALPHA
    assert captured.out.endswith("\n")
    assert "target found" not in captured.out.lower()
    with pytest.raises(json.JSONDecodeError):
        json.loads(captured.out)


def test_export_json_payload(tmp_path, capsys):
    job = _found_job(tmp_path)
    out = tmp_path / "strategy.asb"
    rc = main(
        [
            "export",
            "c1",
            "--run-id",
            job.run_id,
            "--data-dir",
            str(tmp_path),
            "--output",
            str(out),
            "--json",
        ]
    )
    assert rc == 0
    assert zipfile.is_zipfile(out)
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "candidate_id": "c1",
        "exported_path": str(out),
        "research_outcome": "FOUND",
    }


def test_export_without_found_returns_nonzero(tmp_path, capsys):
    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    job = store.create(_spec())
    rc = main(
        [
            "export",
            "c1",
            "--run-id",
            job.run_id,
            "--data-dir",
            str(tmp_path),
            "--output",
            str(tmp_path / "strategy.asb"),
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "FOUND" in err
