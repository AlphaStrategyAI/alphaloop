from __future__ import annotations

import json
import logging
from urllib.error import HTTPError
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
from tests.runtime.test_supervisor import FakeWorker, _cached_spec


def test_http_create_accepts_payload_without_spec_id(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, heartbeat_timeout_s=60.0)
    api = JobAPI(store, sup, tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    try:
        payload = _cached_spec().to_dict()
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
        payload = _cached_spec().to_dict()
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


def test_http_preview_does_not_create_a_job(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    try:
        payload = _cached_spec().to_dict()
        payload.pop("spec_id")
        req = Request(
            f"http://{host}:{port}/v1/jobs/preview",
            data=yaml.safe_dump(payload).encode("utf-8"),
            headers={"Content-Type": "application/yaml"},
            method="POST",
        )
        with urlopen(req) as response:
            assert response.status == 200
            body = json.loads(response.read().decode("utf-8"))
        assert body["ok"] is True
        assert "run_id" not in body
        assert body["planned_n_trials"] >= 1
        assert api.list_jobs()["jobs"] == []
        bad = Request(
            f"http://{host}:{port}/v1/jobs/preview",
            data=b": not yaml object",
            headers={"Content-Type": "application/yaml"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(bad)
        assert exc.value.code == 400
        assert api.list_jobs()["jobs"] == []
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
        created = client.create_run(_cached_spec())
        fetched = client.get_run(created["run_id"])
        assert fetched["run_id"] == created["run_id"]
        cancelled = client.cancel_run(created["run_id"])
        assert cancelled["status"] == "cancelled"
    finally:
        server.shutdown()


def test_http_replay_rewrites_report(tmp_path):
    from alphaloop.contracts.artifacts import RunLayout

    store = JobStore(tmp_path / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    client = JobClient(f"http://{host}:{port}")
    try:
        created = client.create_run(_cached_spec())
        replayed = client.replay_run(created["run_id"])
        assert replayed["run_id"] == created["run_id"]
        report = RunLayout(tmp_path / created["run_id"]).report
        assert report.is_file()
        assert "This report does not claim alpha or future profitability." in report.read_text(
            encoding="utf-8"
        )
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


def test_http_export_found_only(tmp_path):
    import json
    import zipfile

    from alphaloop.contracts.gates import (
        GateResult,
        HardGateName,
        evidence_to_dict,
        evaluate_hard_gates,
    )

    store = JobStore(tmp_path / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    try:
        created = api.create_run(_cached_spec())
        run_id = created["run_id"]
        req = Request(
            f"http://{host}:{port}/v1/jobs/{run_id}/export",
            data=json.dumps({"candidate_id": "c1"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req)
        assert exc.value.code == 409
        job = api.store.get(run_id)
        required = tuple(
            HardGateName(name) for name in job.spec.success_criteria.hard_gates
        )
        evidence = evaluate_hard_gates(
            required,
            tuple(GateResult(name=name, passed=True, detail={}) for name in required),
        )
        evidence_dir = tmp_path / run_id / "evidence"
        evidence_dir.mkdir()
        (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
        (tmp_path / run_id / "trial-ledger.jsonl").write_text(
            json.dumps({"trial_id": "c1", "kind": "momentum_12_1", "parameters": {}})
            + "\n",
            encoding="utf-8",
        )
        api.store.complete_from_artifacts(run_id)
        req = Request(
            f"http://{host}:{port}/v1/jobs/{run_id}/export",
            data=json.dumps({"candidate_id": "c1"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req) as response:
            body = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
        path = tmp_path / run_id / "exports" / "c1.asb"
        assert body["exported_path"] == str(path)
        from alphaloop.runtime.morning import format_export_handoff

        assert body["export_handoff"] == format_export_handoff(
            candidate_id="c1",
            exported_path=str(path),
        )
        assert zipfile.is_zipfile(path)
    finally:
        server.shutdown()


def test_http_dataset_upload_caches_parquet_without_a_job(tmp_path):
    from alphaloop.contracts.artifacts import hash_bytes
    from alphaloop.runtime.dataset_cache import dataset_parquet_path
    from alphaloop.runtime.example_dataset import example_dataset_bytes

    store = JobStore(tmp_path / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    blob = example_dataset_bytes()
    try:
        req = Request(
            f"http://{host}:{port}/v1/datasets",
            data=blob,
            headers={"Content-Type": "application/octet-stream"},
            method="POST",
        )
        with urlopen(req) as response:
            assert response.status == 201
            body = json.loads(response.read().decode("utf-8"))
        digest = hash_bytes(blob)
        assert body["sha256"] == digest
        assert body["dataset_id"] == "ds_" + digest[:16]
        assert dataset_parquet_path(tmp_path, body["dataset_id"]).read_bytes() == blob
        assert api.list_jobs()["jobs"] == []
        bad = Request(
            f"http://{host}:{port}/v1/datasets",
            data=b"not parquet",
            headers={"Content-Type": "application/octet-stream"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(bad)
        assert exc.value.code == 400
        assert api.list_jobs()["jobs"] == []
    finally:
        server.shutdown()


def test_http_dataset_upload_caches_csv_without_a_job(tmp_path):
    import pandas as pd

    from alphaloop.runtime.dataset_cache import dataset_parquet_path

    store = JobStore(tmp_path / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    idx = pd.bdate_range("2018-01-01", periods=5)
    frame = pd.DataFrame({"AAPL": 100.0, "MSFT": 100.0, "SPY": 100.0}, index=idx)
    blob = frame.to_csv().encode("utf-8")
    try:
        req = Request(
            f"http://{host}:{port}/v1/datasets",
            data=blob,
            headers={"Content-Type": "text/csv"},
            method="POST",
        )
        with urlopen(req) as response:
            assert response.status == 201
            body = json.loads(response.read().decode("utf-8"))
        assert str(body["dataset_id"]).startswith("ds_")
        stored = pd.read_parquet(dataset_parquet_path(tmp_path, body["dataset_id"]))
        assert list(stored.columns) == ["AAPL", "MSFT", "SPY"]
        assert api.list_jobs()["jobs"] == []
    finally:
        server.shutdown()


def test_http_dataset_upload_rejects_ohlcv_without_a_job(tmp_path):
    import pandas as pd

    store = JobStore(tmp_path / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    idx = pd.bdate_range("2018-01-01", periods=5)
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1_000_000,
        },
        index=idx,
    )
    blob = frame.to_csv().encode("utf-8")
    try:
        req = Request(
            f"http://{host}:{port}/v1/datasets",
            data=blob,
            headers={"Content-Type": "text/csv"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req)
        assert exc.value.code == 400
        err = exc.value.read().decode("utf-8").lower()
        assert "ohlcv" in err
        assert "found" not in err
        assert api.list_jobs()["jobs"] == []
    finally:
        server.shutdown()
