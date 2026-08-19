from __future__ import annotations

import pytest

from alphaloop.runtime.api import JobAPI
from alphaloop.runtime.client import JobClient
from alphaloop.runtime.daemon import DEFAULT_HOST, UnsupportedBindHost, start_http_server
from alphaloop.runtime.store import JobStore
from alphaloop.runtime.supervisor import Supervisor
from tests.runtime.test_supervisor import FakeWorker, _spec


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
