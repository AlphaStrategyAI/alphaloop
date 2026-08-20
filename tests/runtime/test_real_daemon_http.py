from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import yaml

from alphaloop.runtime.example_dataset import example_dataset_ref
from alphaloop.runtime.preflight import HOST_CONSTRAINT


def _payload(**overrides):
    ref = example_dataset_ref()
    body = {
        "statement": "12-1 momentum works in US large caps net of costs",
        "economic_logic": "past winners continue",
        "signal_mechanism": "momentum_12_1",
        "market_scope": "AAPL, MSFT",
        "market_profile": "us-equity-daily",
        "benchmark": "SPY",
        "hard_gates": ["dsr", "walk_forward", "vs_benchmark"],
        "seed": 7,
        "time_budget_s": 30,
        "cost_budget_usd": 1.0,
        "dataset": {"dataset_id": ref.dataset_id, "sha256": ref.sha256},
    }
    body.update(overrides)
    return body


def _post_yaml(base_url: str, payload: dict):
    req = Request(
        base_url + "/v1/jobs",
        data=yaml.safe_dump(payload).encode("utf-8"),
        headers={"Content-Type": "application/yaml"},
        method="POST",
    )
    return urlopen(req)


def test_yaml_submit_without_spec_id(real_daemon):
    with _post_yaml(real_daemon["base_url"], _payload()) as response:
        assert response.status == 201
        body = json.loads(response.read().decode("utf-8"))
    assert body["run_id"].startswith("j_")
    assert body["host_constraint"] == HOST_CONSTRAINT


def test_empty_hard_gates_rejected_without_job(real_daemon):
    try:
        _post_yaml(real_daemon["base_url"], _payload(hard_gates=[]))
        raise AssertionError("expected HTTPError")
    except HTTPError as exc:
        assert exc.code == 400
        body = json.loads(exc.read().decode("utf-8"))
        assert any("hard gate" in err.lower() for err in body.get("errors", []))
    listed = json.loads(urlopen(real_daemon["base_url"] + "/v1/jobs").read().decode("utf-8"))
    assert listed.get("jobs") == []


def test_unknown_dsl_kind_rejected_without_job(real_daemon):
    try:
        _post_yaml(real_daemon["base_url"], _payload(signal_mechanism="not-a-dsl-kind"))
        raise AssertionError("expected HTTPError")
    except HTTPError as exc:
        assert exc.code == 400
    listed = json.loads(urlopen(real_daemon["base_url"] + "/v1/jobs").read().decode("utf-8"))
    assert listed.get("jobs") == []


def test_missing_declared_dataset_rejected_without_job(real_daemon):
    payload = _payload(
        dataset={"dataset_id": "ds_missing", "sha256": "0" * 64},
    )
    # DatasetRef validates shape when going through ResearchSpec; YAML dict is enough.
    try:
        _post_yaml(real_daemon["base_url"], payload)
        raise AssertionError("expected HTTPError")
    except HTTPError as exc:
        assert exc.code == 400
        body = json.loads(exc.read().decode("utf-8"))
        assert any("dataset" in err.lower() for err in body.get("errors", []))
    listed = json.loads(urlopen(real_daemon["base_url"] + "/v1/jobs").read().decode("utf-8"))
    assert listed.get("jobs") == []


def test_root_and_app_js_from_real_daemon(real_daemon):
    html = urlopen(real_daemon["base_url"] + "/").read().decode("utf-8")
    assert "FOUND" in html
    assert "NO_EVIDENCE" in html
    assert "INCONCLUSIVE" in html
    assert 'id="spec-yaml"' in html
    script = urlopen(real_daemon["base_url"] + "/app.js").read().decode("utf-8")
    assert "application/yaml" in script
    assert "override" not in script.lower()
