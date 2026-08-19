from __future__ import annotations

import json
import logging
from urllib.request import Request, urlopen

import pytest
import yaml

from alphaloop.runtime.api import JobAPI
from alphaloop.runtime.client import JobClient
from alphaloop.runtime.daemon import (
    DEFAULT_HOST,
    UnsupportedBindHost,
    _safe_tick,
    start_http_server,
)
from alphaloop.runtime.store import JobStore
from alphaloop.runtime.supervisor import Supervisor
from tests.runtime.test_supervisor import FakeWorker, _spec


def test_http_create_accepts_payload_without_spec_id(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, heartbeat_timeout_s=60.0)
    api = JobAPI(store, sup, tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    try:
        payload = _spec().to_dict()
        payload.pop("spec_id")
        req = Request(
            f"http://{host}:{port}/v1/jobs",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req) as response:
            body = json.loads(response.read().decode("utf-8"))
            assert response.status == 201
            assert body["run_id"].startswith("j_")
            assert body["host_constraint"]
    finally:
        server.shutdown()


def test_http_create_accepts_yaml_body(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    try:
        payload = _spec().to_dict()
        payload.pop("spec_id")
        req = Request(
            f"http://{host}:{port}/v1/jobs",
            data=yaml.safe_dump(payload).encode("utf-8"),
            headers={"Content-Type": "application/yaml"},
            method="POST",
        )
        with urlopen(req) as response:
            assert response.status == 201
            body = json.loads(response.read().decode("utf-8"))
            assert "run_id" in body
    finally:
        server.shutdown()


def test_http_create_get_cancel(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, heartbeat_timeout_s=60.0)
    api = JobAPI(store, sup, tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    client = JobClient(f"http://{host}:{port}")
    try:
        assert client.healthz()["status"] == "ok"
        created = client.create_run(_spec())
        fetched = client.get_run(created["run_id"])
        assert fetched["run_id"] == created["run_id"]
        cancelled = client.cancel_run(created["run_id"])
        assert cancelled["status"] == "cancelled"
    finally:
        server.shutdown()


def test_non_loopback_bind_rejected(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    with pytest.raises(UnsupportedBindHost):
        start_http_server(api, "0.0.0.0", 8765)


def test_safe_tick_logs_failure_and_allows_next_tick(caplog):
    class FlakySupervisor:
        def __init__(self):
            self.calls = 0

        def tick(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient tick failure")

    supervisor = FlakySupervisor()
    with caplog.at_level(logging.ERROR, logger="alphaloop.runtime.daemon"):
        _safe_tick(supervisor)
        _safe_tick(supervisor)

    assert supervisor.calls == 2
    assert "supervisor tick failed" in caplog.text
    assert "transient tick failure" in caplog.text
