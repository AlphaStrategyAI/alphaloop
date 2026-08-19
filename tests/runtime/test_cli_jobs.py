from __future__ import annotations

import json

import yaml

from alphaloop.cli.main import create_parser, main
from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import GateResult, HardGateName, evidence_to_dict, evaluate_hard_gates
from alphaloop.runtime.preflight import HOST_CONSTRAINT
from tests.runtime.test_supervisor import _spec


def test_parser_has_runtime_commands():
    parser = create_parser()
    assert "start" in parser.format_help()
    assert "submit" in parser.format_help()


def test_submit_without_daemon_fails(tmp_path, capsys):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    rc = main(["submit", "--spec", str(spec_path), "--data-dir", str(tmp_path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "alphaloop start" in err


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
    spec_path.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    try:
        rc = main(["submit", "--spec", str(spec_path), "--data-dir", str(tmp_path)])
        captured = capsys.readouterr()
        assert rc == 0
        assert HOST_CONSTRAINT in captured.out
        assert "j_" in captured.out
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
    assert "FOUND" in captured.out
    assert layout.report.is_file()
    assert "FOUND" in layout.report.read_text(encoding="utf-8")
