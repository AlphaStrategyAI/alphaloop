from __future__ import annotations

import yaml

from alphaloop.cli.main import create_parser, main
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
