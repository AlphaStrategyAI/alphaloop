from __future__ import annotations

import subprocess
import sys
from importlib.resources import files
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from alphaloop.contracts.gates import HardGateName
from alphaloop.contracts.research_spec import ALLOWED_PROFILES
from alphaloop.protocol.dsl import DIRECTIONAL_SIGNAL_KINDS
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
    assert "dataset.runId" in script
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
    assert "dataset.runId" in script
    assert "override" not in script.lower()
    assert "56rem" in css or "min-width: 56rem" in css


def test_packaged_guided_form_preview_grid_and_job_cards():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="hypothesis-form"' in html
    assert 'id="field-statement"' in html
    assert 'id="field-economic-logic"' in html
    assert 'id="field-signal-mechanism"' in html
    assert 'id="field-market-scope"' in html
    assert 'id="field-market-profile"' in html
    assert 'id="field-benchmark"' in html
    assert 'id="field-hard-gates"' in html
    assert 'id="field-seed"' in html
    assert 'id="field-time-budget"' in html
    assert 'id="field-cost-budget"' in html
    for kind in DIRECTIONAL_SIGNAL_KINDS:
        assert f'value="{kind}"' in html
    assert 'value="parkinson_hist_vol"' not in html
    assert 'value="obv_slope"' not in html
    for profile in ALLOWED_PROFILES:
        assert f'value="{profile}"' in html
    for gate in HardGateName:
        assert f'value="{gate.value}"' in html
    assert "dataset.runId" in script
    assert "protocol-grid" in script
    assert "JSON.stringify(body.method_parameter_grid)" not in script
    assert "job.hypothesis" in script
    assert "n_trials" in script
    assert 'id="funnel-summary"' in html
    assert "failure_counts" in script
    assert "n_evaluated" in script
    assert "load-queued" in script
    assert "override" not in script.lower()
    assert "override" not in html.lower()
    assert "input:focus-visible" in css


def test_packaged_queued_followup_auto_preview():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    load_at = script.find("function loadQueuedHypothesis")
    example_at = script.find("const EXAMPLE_SPEC")
    assert load_at != -1
    assert example_at != -1
    body = script[load_at:example_at]
    assert "previewProtocol()" in body
    assert "submitJob()" not in body
    assert "dataset" in body
    assert "time_budget_s" in body
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_funnel_bars():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="funnel-bars"' in html
    assert "funnel-stack" in script
    assert "funnel-seg" in script
    assert "dataset.pct" in script
    assert "incomplete:" in script
    assert "funnel-fail-fill" in script
    assert ".funnel-stack" in css
    assert '.funnel-seg[data-key="passed"]' in css
    assert '.funnel-seg[data-key="failed"]' in css
    assert '.funnel-seg[data-key="incomplete"]' in css
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_search_progress():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="search-progress"' in html
    assert "search: " in script
    assert "search-progress-fill" in script
    assert "planned_n_trials" in script
    assert ".search-progress" in css
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_morning_lead_and_job_funnel():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert "fillFunnelStack" in script
    assert "job-funnel" in script
    assert "aria-current" in script
    assert "detail.hidden" in script
    assert ".job-funnel .funnel-stack" in css
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_qualifying_candidates():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    assert 'id="qualifying"' in html
    assert html.find('id="qualifying"') < html.find('id="evidence"')
    assert "qualifying_candidates" in script
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_console_asb_export():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    assert 'id="export-status"' in html
    assert "export-asb" in script
    assert "/export" in script
    assert "exported_path" in script
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_console_morning_report():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="report"' in html
    assert html.find('id="stop-reason"') < html.find('id="report"')
    assert html.find('id="report"') < html.find('id="qualifying"')
    assert "report_markdown" in script
    assert "fillReport" in script
    assert "grid-template-columns" in css
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_console_morning_verdict_stage():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="verdict"' in html
    assert 'id="outcome-gloss"' in html
    assert html.find('id="outcome"') < html.find('id="outcome-gloss"')
    assert html.find('id="outcome-gloss"') < html.find('id="job-status"')
    assert 'id="help-no-evidence"' in html
    assert 'id="help-inconclusive"' in html
    assert (
        "NO_EVIDENCE means a required hard gate failed. It is not a promise that alpha does not exist."
        in html
    )
    assert (
        "INCONCLUSIVE means the evidence set is incomplete. Missing diagnostics cannot produce FOUND."
        in html
    )
    assert "fillOutcomeGloss" in script
    assert "help-found" in script
    assert "repeating-linear-gradient" in css
    assert "font-variant-numeric" in css
    assert "clamp(" in css
    assert "http" not in css.lower()
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


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
