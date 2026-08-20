from __future__ import annotations

import subprocess
import sys
from importlib.resources import files
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from alphaloop.runtime.api import JobAPI
from alphaloop.runtime.client import JobClient
from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server
from alphaloop.runtime.preflight import HOST_CONSTRAINT
from alphaloop.runtime.store import JobStore
from alphaloop.runtime.supervisor import Supervisor
from tests.runtime.test_supervisor import FakeWorker, _spec


def test_packaged_assets_are_read_only_morning_copy():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    assert "/app.js" in html
    assert "FOUND" in html
    assert "NO_EVIDENCE" in html
    assert "INCONCLUSIVE" in html
    assert 'id="spec-yaml"' in html
    assert 'id="submit-job"' in html
    assert 'id="preview-protocol"' in html
    assert 'id="protocol-preview"' in html
    assert "disabled" in html
    assert 'job.run_id + " — " + job.status + " — " + job.research_outcome' in script
    assert "application/yaml" in script
    assert "setInterval" in script
    assert "/v1/jobs" in script
    assert "override" not in script.lower()
    assert "hard_gates=" not in script


def test_packaged_help_and_evidence_lines():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    assert 'id="help"' in html
    assert 'id="help-no-alpha"' in html
    assert "This console does not claim alpha or future profitability." in html
    assert 'id="help-status"' in html
    assert (
        "Job status (queued, running, completed, failed, cancelled) is not the research conclusion."
        in html
    )
    assert 'id="help-host"' in html
    assert HOST_CONSTRAINT in html
    assert 'id="help-found"' in html
    assert (
        "FOUND means every required hard gate is present and passed. It is not a promise of alpha."
        in html
    )
    assert "job.evidence_lines" in script
    assert "/v1/jobs/preview" in script
    assert "override" not in script.lower()


def test_packaged_example_layout_and_job_controls():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="load-example"' in html
    assert 'id="before-bed"' in html
    assert 'id="morning"' in html
    assert 'id="cancel-job"' in html
    assert 'id="resume-job"' in html
    assert "statement: 12-1 momentum works in US large caps net of costs" in script
    assert "signal_mechanism: momentum_12_1" in script
    assert 'postJobAction("cancel")' in script
    assert 'postJobAction("resume")' in script
    assert 'job.run_id + " — " + job.status + " — " + job.research_outcome' in script
    assert "override" not in script.lower()
    assert "56rem" in css or "min-width: 56rem" in css


def test_static_package_loads_without_fastapi():
    """Morning assets must load even when FastAPI is not installed."""
    code = r"""
import sys
from importlib.abc import MetaPathFinder
from importlib.resources import files


class BlockFastAPI(MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "fastapi" or fullname.startswith("fastapi."):
            raise ModuleNotFoundError("No module named 'fastapi'")
        return None


sys.meta_path.insert(0, BlockFastAPI())
for name in list(sys.modules):
    if name == "fastapi" or name.startswith("fastapi.") or name.startswith("alphaloop.webui"):
        del sys.modules[name]

html = files("alphaloop.webui.static").joinpath("index.html").read_text(encoding="utf-8")
assert "FOUND" in html
assert "NO_EVIDENCE" in html
assert "INCONCLUSIVE" in html
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _server(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, heartbeat_timeout_s=60.0)
    api = JobAPI(store, sup, tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}"


def test_root_serves_packaged_html(tmp_path):
    server, base = _server(tmp_path)
    try:
        with urlopen(base + "/") as response:
            assert response.headers.get_content_type() == "text/html"
            body = response.read().decode("utf-8")
        assert "FOUND" in body
        assert "NO_EVIDENCE" in body
        assert "INCONCLUSIVE" in body
        assert "/app.js" in body
        assert "spec-yaml" in body
        assert 'id="help"' in body
        assert HOST_CONSTRAINT in body
    finally:
        server.shutdown()


def test_static_javascript_and_css(tmp_path):
    server, base = _server(tmp_path)
    try:
        with urlopen(base + "/app.js") as response:
            assert "javascript" in response.headers.get_content_type()
            script = response.read().decode("utf-8")
        assert "/v1/jobs" in script
        assert "override" not in script.lower()
        with urlopen(base + "/styles.css") as response:
            assert response.headers.get_content_type() == "text/css"
            css = response.read().decode("utf-8")
        assert '[data-outcome="FOUND"]' in css
        assert '[data-outcome="NO_EVIDENCE"]' in css
        assert '[data-outcome="INCONCLUSIVE"]' in css
    finally:
        server.shutdown()


def test_list_jobs_http(tmp_path):
    server, base = _server(tmp_path)
    client = JobClient(base)
    try:
        created = client.create_run(_spec())
        listed = client.list_jobs()
        assert listed["jobs"][0]["run_id"] == created["run_id"]
        assert "research_outcome" in listed["jobs"][0]
        assert listed["jobs"][0]["evidence_lines"] == []
    finally:
        server.shutdown()


@pytest.mark.parametrize("method", ["PUT", "PATCH", "POST"])
def test_gate_override_is_not_found(tmp_path, method):
    server, base = _server(tmp_path)
    try:
        request = Request(
            base + "/v1/jobs/j_x/gates",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(request)
        assert exc.value.code == 404
    finally:
        server.shutdown()


def test_static_path_traversal_rejected(tmp_path):
    server, base = _server(tmp_path)
    try:
        with pytest.raises(HTTPError) as exc:
            urlopen(base + "/../runtime/api.py")
        assert exc.value.code == 404
    finally:
        server.shutdown()
