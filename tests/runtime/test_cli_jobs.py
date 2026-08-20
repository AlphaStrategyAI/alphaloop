from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from alphaloop.cli.main import create_parser, main
from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import GateResult, HardGateName, evidence_to_dict, evaluate_hard_gates
from alphaloop.contracts.status import JobStatus
from alphaloop.runtime.morning import EMPTY_STATUS_CUE, STATUS_NO_ALPHA
from alphaloop.runtime.preflight import HOST_CONSTRAINT
from tests.runtime.test_supervisor import _cached_spec, _spec


def test_parser_has_runtime_commands():
    parser = create_parser()
    assert "start" in parser.format_help()
    assert "submit" in parser.format_help()
    assert "preview" in parser.format_help()
    assert "soak" in parser.format_help()


def test_submit_without_daemon_fails(tmp_path, capsys):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    rc = main(["submit", "--spec", str(spec_path), "--data-dir", str(tmp_path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "alphaloop start" in err


def test_preview_without_daemon_fails(tmp_path, capsys):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(_cached_spec().to_dict()), encoding="utf-8")
    rc = main(["preview", "--spec", str(spec_path), "--data-dir", str(tmp_path)])
    assert rc == 2
    assert "alphaloop start" in capsys.readouterr().err


def test_submit_returns_run_id_and_host_constraint(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(_cached_spec().to_dict()), encoding="utf-8")
    try:
        rc = main(["submit", "--spec", str(spec_path), "--data-dir", str(tmp_path)])
        captured = capsys.readouterr()
        assert rc == 0
        assert HOST_CONSTRAINT in captured.out
        assert "j_" in captured.out
    finally:
        server.shutdown()


def test_preview_shows_protocol_without_creating_a_job(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(_cached_spec().to_dict()), encoding="utf-8")
    try:
        rc = main(["preview", "--spec", str(spec_path), "--data-dir", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "planned_n_trials:" in out
        assert "spec_id:" in out
        assert HOST_CONSTRAINT in out
        assert "Freeze with alphaloop submit --spec PATH" in out
        assert "This preview does not claim alpha or future profitability." in out
        assert "run_id:" not in out
        assert "target found" not in out.lower()
        assert api.list_jobs()["jobs"] == []

        rc = main(
            ["preview", "--spec", str(spec_path), "--json", "--data-dir", str(tmp_path)]
        )
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["ok"] is True
        assert "run_id" not in payload
        assert payload["planned_n_trials"] >= 1
        assert api.list_jobs()["jobs"] == []
    finally:
        server.shutdown()


def test_preview_missing_dataset_is_not_ok_and_creates_no_job(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    try:
        rc = main(["preview", "--spec", str(spec_path), "--data-dir", str(tmp_path)])
        captured = capsys.readouterr()
        assert rc == 2
        assert "dataset snapshot is required" in captured.out
        assert "Freeze with alphaloop submit" not in captured.out
        assert api.list_jobs()["jobs"] == []
    finally:
        server.shutdown()


def test_status_parser_has_json_flag():
    parser = create_parser()
    args = parser.parse_args(["status", "j_x", "--json"])
    assert args.json is True
    assert parser.parse_args(["status", "j_x"]).json is False


def test_status_parser_run_id_optional():
    parser = create_parser()
    args = parser.parse_args(["status", "--json"])
    assert args.run_id is None
    assert args.json is True
    assert parser.parse_args(["status", "j_x"]).run_id == "j_x"


def test_status_without_run_id_leads_with_latest_or_empty(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    try:
        rc = main(["status", "--data-dir", str(tmp_path)])
        empty = capsys.readouterr()
        assert rc == 0
        assert empty.out == EMPTY_STATUS_CUE
        assert "alphaloop preview --spec PATH" in empty.out
        assert "target found" not in empty.out.lower()
        assert STATUS_NO_ALPHA in empty.out

        rc = main(["status", "--json", "--data-dir", str(tmp_path)])
        empty_json = capsys.readouterr()
        assert rc == 0
        assert json.loads(empty_json.out) == {"jobs": []}

        store.create(_spec(), run_id="j_aaa")
        newest = store.create(_spec(), run_id="j_zzz")
        rc = main(["status", "--data-dir", str(tmp_path)])
        human = capsys.readouterr()
        assert rc == 0
        assert human.out.splitlines()[0] == f"run_id: {newest.run_id}"
        assert human.out.splitlines()[1] == "NONE"
        assert STATUS_NO_ALPHA in human.out

        rc = main(["status", "--json", "--data-dir", str(tmp_path)])
        machine = capsys.readouterr()
        payload = json.loads(machine.out)
        assert payload["run_id"] == newest.run_id
        assert payload["research_outcome"] == "NONE"
    finally:
        server.shutdown()


def test_status_default_is_verdict_json_is_payload(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    try:
        job = store.create(_spec())
        rc = main(["status", job.run_id, "--data-dir", str(tmp_path)])
        human = capsys.readouterr()
        assert rc == 0
        assert human.out.splitlines()[0] == "NONE"
        assert "This status does not claim alpha or future profitability." in human.out
        with pytest.raises(json.JSONDecodeError):
            json.loads(human.out)

        rc = main(["status", job.run_id, "--json", "--data-dir", str(tmp_path)])
        machine = capsys.readouterr()
        assert rc == 0
        payload = json.loads(machine.out)
        assert payload["run_id"] == job.run_id
        assert payload["research_outcome"] == "NONE"
        assert "report_markdown" in payload
    finally:
        server.shutdown()


def test_status_missing_run_surfaces_http_error_without_start_hint(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    try:
        rc = main(["status", "j_missing", "--data-dir", str(tmp_path)])
        captured = capsys.readouterr()
        assert rc == 2
        assert "404" in captured.err
        assert "job not found" in captured.err
        assert "alphaloop start" not in captured.err
    finally:
        server.shutdown()


def test_cancel_and_resume_parser_have_json_flag():
    parser = create_parser()
    assert parser.parse_args(["cancel", "j_x", "--json"]).json is True
    assert parser.parse_args(["resume", "j_x"]).json is False
    assert parser.parse_args(["cancel"]).run_id is None
    assert parser.parse_args(["resume"]).run_id is None


def test_cancel_default_is_verdict_json_is_payload(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    try:
        job = store.create(_spec())
        rc = main(["cancel", job.run_id, "--data-dir", str(tmp_path)])
        human = capsys.readouterr()
        assert rc == 0
        assert human.out.splitlines()[0] == "INCONCLUSIVE"
        assert "Job status: cancelled" in human.out
        assert STATUS_NO_ALPHA in human.out
        assert "target found" not in human.out.lower()
        with pytest.raises(json.JSONDecodeError):
            json.loads(human.out)

        rc = main(["cancel", job.run_id, "--json", "--data-dir", str(tmp_path)])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["status"] == "cancelled"
        assert payload["research_outcome"] == "INCONCLUSIVE"
    finally:
        server.shutdown()


def test_cancel_without_run_id_uses_latest(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    try:
        older = store.create(_spec())
        newest = store.create(_spec())
        rc = main(["cancel", "--data-dir", str(tmp_path)])
        human = capsys.readouterr()
        assert rc == 0
        assert human.out.splitlines()[0] == f"run_id: {newest.run_id}"
        assert human.out.splitlines()[1] == "INCONCLUSIVE"
        assert "Job status: cancelled" in human.out
        assert store.get(newest.run_id).status is JobStatus.CANCELLED
        assert store.get(older.run_id).status is JobStatus.QUEUED
        assert "target found" not in human.out.lower()
        with pytest.raises(json.JSONDecodeError):
            json.loads(human.out)
    finally:
        server.shutdown()


def test_cancel_without_run_id_empty_store(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    try:
        rc = main(["cancel", "--data-dir", str(tmp_path)])
        captured = capsys.readouterr()
        assert rc == 2
        assert captured.err == "error: no overnight job yet\n"
        assert "FOUND" not in captured.out
        assert "target found" not in captured.err.lower()
    finally:
        server.shutdown()


def test_resume_without_run_id_uses_latest(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    try:
        store.create(_spec())
        newest = store.create(_spec())
        store.update_status(newest.run_id, JobStatus.FAILED, error="worker crashed")
        rc = main(["resume", "--data-dir", str(tmp_path)])
        human = capsys.readouterr()
        assert rc == 0
        assert human.out.splitlines()[0] == f"run_id: {newest.run_id}"
        assert "Job status: queued" in human.out
        assert store.get(newest.run_id).status is JobStatus.QUEUED
    finally:
        server.shutdown()


def test_resume_default_is_verdict_json_is_payload(tmp_path, capsys):
    from alphaloop.runtime.api import JobAPI
    from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server, write_daemon_meta
    from alphaloop.runtime.store import JobStore
    from alphaloop.runtime.supervisor import Supervisor
    from tests.runtime.test_supervisor import FakeWorker

    store = JobStore(tmp_path / ".alphaloop" / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    write_daemon_meta(tmp_path, host=host, port=port, pid=0)
    try:
        job = store.create(_spec())
        store.update_status(job.run_id, JobStatus.FAILED, error="worker crashed")
        rc = main(["resume", job.run_id, "--data-dir", str(tmp_path)])
        human = capsys.readouterr()
        assert rc == 0
        assert human.out.splitlines()[0] == "NONE"
        assert "Job status: queued" in human.out
        assert STATUS_NO_ALPHA in human.out
        with pytest.raises(json.JSONDecodeError):
            json.loads(human.out)

        rc = main(["resume", job.run_id, "--json", "--data-dir", str(tmp_path)])
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["status"] == "queued"
        assert payload["research_outcome"] == "NONE"
    finally:
        server.shutdown()


def test_parser_has_top_level_replay():
    parser = create_parser()
    assert "replay" in parser.format_help()


def test_replay_missing_run_dir_returns_2(tmp_path, capsys):
    rc = main(["replay", "j_missing", "--data-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 2
    assert "j_missing" in captured.err or "not found" in captured.err.lower() or "missing" in captured.err.lower()


def test_replay_rewrites_report_without_looprunner(tmp_path, capsys):
    layout = RunLayout(tmp_path / "j_replay")
    layout.run_dir.mkdir()
    layout.research_spec.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    evidence = evaluate_hard_gates(
        (HardGateName.DSR,),
        (GateResult(name=HardGateName.DSR, passed=True, detail={}),),
    )
    layout.evidence.mkdir()
    (layout.evidence / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    rc = main(["replay", "j_replay", "--data-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.splitlines()[0] == "FOUND"
    assert "FOUND means every required hard gate is present and passed." in captured.out
    assert "Primary evidence:" in captured.out
    assert "Stop reason: all_gates_passed" in captured.out
    assert "Job status:" in captured.out
    assert STATUS_NO_ALPHA in captured.out
    assert "research_outcome:" not in captured.out
    assert "target found" not in captured.out.lower()
    with pytest.raises(json.JSONDecodeError):
        json.loads(captured.out)
    assert layout.report.is_file()
    assert "FOUND" in layout.report.read_text(encoding="utf-8")


def test_replay_parser_has_json_flag():
    parser = create_parser()
    assert parser.parse_args(["replay", "j_x", "--json"]).json is True
    assert parser.parse_args(["replay", "j_x"]).json is False


def test_replay_json_is_artifact_view(tmp_path, capsys):
    layout = RunLayout(tmp_path / "j_replay")
    layout.run_dir.mkdir()
    layout.research_spec.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    evidence = evaluate_hard_gates(
        (HardGateName.DSR,),
        (GateResult(name=HardGateName.DSR, passed=True, detail={}),),
    )
    layout.evidence.mkdir()
    (layout.evidence / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    rc = main(["replay", "j_replay", "--json", "--data-dir", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["research_outcome"] == "FOUND"
    assert payload["stop_reason"] == "all_gates_passed"


def test_soak_emits_release_plan_without_starting_jobs(capsys):
    rc = main(["soak"])
    out = capsys.readouterr().out
    assert rc == 0
    assert HOST_CONSTRAINT in out
    assert "This checklist is not CI." in out
    assert "This soak does not claim alpha or future profitability." in out
    assert "us-equity-daily" in out
    assert "crypto-daily" in out
    assert "FOUND" in out
    assert "NO_EVIDENCE" in out
    assert "INCONCLUSIVE" in out
    assert "primary evidence" in out
    assert "stop reason" in out
    assert "kill -9" in out
    assert "trial_id" in out
    assert "target found" not in out.lower()


def test_ci_workflow_does_not_run_soak():
    text = Path(".github/workflows/pytest.yml").read_text(encoding="utf-8")
    assert "soak" not in text.lower()
