"""
Tests for the v0.7.1 WebUI FastAPI JSON backend.

Verifies the 7 endpoints + /healthz behave correctly against a
synthetic sample run directory.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from alphaloop.webui import create_app
from alphaloop.webui.data import (
    DEFAULT_DAG_NODES,
    DEFAULT_DAG_EDGES,
    DIAGNOSTIC_LABELS,
)


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


@pytest.fixture
def runs_dir():
    """Build a synthetic runs/ directory with one populated run."""
    tmp = Path(tempfile.mkdtemp(prefix="alphaloop-webapi-test-"))
    run_id = "2026-08-16T00-00-00Z_aabbccdd"
    run_dir = tmp / run_id
    run_dir.mkdir(parents=True)

    # manifest.yaml
    manifest = {
        "run_id": run_id,
        "goal": "test goal",
        "seed": 42,
        "git_commit": "abc1234567890",
        "llm_model": "gpt-4o-mini",
        "target_dsr": 1.0,
        "budget_usd": 5.0,
        "timeout_s": 21600,
        "started_at": "2026-08-16T00:00:00Z",
        "finished_at": "2026-08-16T00:10:00Z",
        "termination_reason": "B",
        "estimated_cost_usd": 0.05,
        "task_count": 5,
    }
    (run_dir / "manifest.yaml").write_text(
        "\n".join(f"{k}: {v}" for k, v in manifest.items()) + "\n",
        encoding="utf-8",
    )

    # top5.json
    top5 = {
        "run_id": run_id,
        "termination_reason": "B",
        "top5": [
            {
                "rank": i,
                "task_id": f"task-{i:04d}",
                "strategy": f"Strategy{i}",
                "factor": "Momentum12M",
                "params": {"lookback": 12 * i},
                "dsr": 0.6 + 0.05 * (5 - i),
                "sharpe": 1.0 + 0.1 * (5 - i),
                "cagr": 0.15,
                "max_dd": 0.05,
                "passes_all": True,
                "one_line_thesis": f"Top {i}",
            }
            for i in range(1, 6)
        ],
    }
    (run_dir / "top5.json").write_text(
        json.dumps(top5, indent=2, sort_keys=True), encoding="utf-8"
    )

    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def client(runs_dir):
    app = create_app(runs_dir=runs_dir)
    from fastapi.testclient import TestClient

    return TestClient(app)


# ---------------------------------------------------------------------
# /healthz
# ---------------------------------------------------------------------


def test_healthz_returns_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "runs_dir" in body
    assert "n_runs" in body
    assert body["n_runs"] >= 1


def test_healthz_shows_run_count(runs_dir, client):
    r = client.get("/healthz")
    assert r.json()["n_runs"] == 1


# ---------------------------------------------------------------------
# /api/runs
# ---------------------------------------------------------------------


def test_list_runs_returns_array(client):
    r = client.get("/api/runs")
    assert r.status_code == 200
    body = r.json()
    assert "runs" in body
    assert isinstance(body["runs"], list)
    assert len(body["runs"]) == 1
    assert "rid" in body["runs"][0]
    assert "started_at" in body["runs"][0]


# ---------------------------------------------------------------------
# /api/runs/{rid}/top5
# ---------------------------------------------------------------------


def test_top5_returns_five_picks(client):
    rids = [r["rid"] for r in client.get("/api/runs").json()["runs"]]
    rid = rids[0]
    r = client.get(f"/api/runs/{rid}/top5")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert body["rid"] == rid
    assert "top5" in body
    assert len(body["top5"]) == 5
    for p in body["top5"]:
        assert {"rank", "task_id", "dsr", "sharpe"}.issubset(p.keys())


def test_top5_includes_metrics_summary(client):
    rids = [r["rid"] for r in client.get("/api/runs").json()["runs"]]
    r = client.get(f"/api/runs/{rids[0]}/top5")
    body = r.json()
    assert "metrics" in body
    assert body["metrics"]["n_picks"] == 5
    assert body["metrics"]["best_dsr"] > 0.0


# ---------------------------------------------------------------------
# /api/runs/{rid}/strategies/{sid}
# ---------------------------------------------------------------------


def test_strategy_detail_returns_diagnostics(client):
    rids = [r["rid"] for r in client.get("/api/runs").json()["runs"]]
    top5 = client.get(f"/api/runs/{rids[0]}/top5").json()["top5"]
    sid = top5[0]["task_id"]
    r = client.get(f"/api/runs/{rids[0]}/strategies/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert "diagnostics" in body
    assert {f"q{i}" for i in range(1, 8)}.issubset(body["diagnostics"].keys())
    assert "equity" in body
    assert len(body["equity"]) > 0
    assert "pick" in body


def test_strategy_detail_falls_back_to_first_pick(client):
    rids = [r["rid"] for r in client.get("/api/runs").json()["runs"]]
    r = client.get(f"/api/runs/{rids[0]}/strategies/nonexistent-strategy-id")
    assert r.status_code == 200
    body = r.json()
    assert "pick" in body


# ---------------------------------------------------------------------
# /api/runs/{rid}/diagnostics
# ---------------------------------------------------------------------


def test_diagnostics_returns_radar_and_bar(client):
    rids = [r["rid"] for r in client.get("/api/runs").json()["runs"]]
    r = client.get(f"/api/runs/{rids[0]}/diagnostics")
    assert r.status_code == 200
    body = r.json()
    assert "radar" in body
    assert len(body["radar"]) == 7
    assert "bar" in body
    assert len(body["bar"]) == 7
    assert "manifest" in body
    assert body["manifest"]["run_id"] == rids[0]


def test_diagnostics_radar_axis_labels(client):
    rids = [r["rid"] for r in client.get("/api/runs").json()["runs"]]
    r = client.get(f"/api/runs/{rids[0]}/diagnostics")
    body = r.json()
    expected_labels = {label for _, label, _ in DIAGNOSTIC_LABELS}
    actual_labels = {p["axis"] for p in body["radar"]}
    assert expected_labels == actual_labels


def test_diagnostics_bar_includes_pass_count(client):
    rids = [r["rid"] for r in client.get("/api/runs").json()["runs"]]
    r = client.get(f"/api/runs/{rids[0]}/diagnostics")
    body = r.json()
    for b in body["bar"]:
        assert "pass_rate" in b
        assert "pass_count" in b
        assert "total" in b
        assert "category" in b
        assert b["category"] in ("math", "stats", "ai")


def test_diagnostics_compare_overlay(client):
    rids = [r["rid"] for r in client.get("/api/runs").json()["runs"]]
    r = client.get(f"/api/runs/{rids[0]}/diagnostics?compare={rids[0]}")
    assert r.status_code == 200
    body = r.json()
    assert "compare_with" in body
    assert body["compare_with"] is not None
    assert len(body["compare_with"]) == 7


# ---------------------------------------------------------------------
# /api/runs/{rid}/replay
# ---------------------------------------------------------------------


def test_replay_returns_dag_and_timing(client):
    rids = [r["rid"] for r in client.get("/api/runs").json()["runs"]]
    r = client.get(f"/api/runs/{rids[0]}/replay")
    assert r.status_code == 200
    body = r.json()
    assert "dag" in body
    assert len(body["dag"]["nodes"]) == 6
    assert len(body["dag"]["edges"]) == 5
    assert "timing" in body
    assert len(body["timing"]) == 6
    for node_id in [n["id"] for n in DEFAULT_DAG_NODES]:
        assert node_id in body["timing"]


def test_replay_dag_topology_matches(client):
    rids = [r["rid"] for r in client.get("/api/runs").json()["runs"]]
    r = client.get(f"/api/runs/{rids[0]}/replay")
    body = r.json()
    edges = body["dag"]["edges"]
    for expected in DEFAULT_DAG_EDGES:
        assert expected in edges


# ---------------------------------------------------------------------
# /api/runs/{rid}/stream (SSE)
# ---------------------------------------------------------------------


def test_stream_returns_sse_when_done(client):
    rids = [r["rid"] for r in client.get("/api/runs").json()["runs"]]
    with client.stream("GET", f"/api/runs/{rids[0]}/stream") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        # Read first chunk
        chunks = []
        for chunk in r.iter_text():
            chunks.append(chunk)
            if "complete" in chunk or len(chunks) >= 3:
                break
        assert any("event:" in c for c in chunks)


# ---------------------------------------------------------------------
# /api/runs/{rid}/export
# ---------------------------------------------------------------------


def test_export_returns_self_contained_html(client):
    rids = [r["rid"] for r in client.get("/api/runs").json()["runs"]]
    r = client.get(f"/api/runs/{rids[0]}/export")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text
    assert "<!DOCTYPE html>" in body
    assert "<style>" in body
    assert rids[0] in body
    assert "Top 5 picks" in body
    # CSV-sized budget
    assert len(r.content) < 500_000


# ---------------------------------------------------------------------
# 404 path
# ---------------------------------------------------------------------


def test_404_for_unknown_run(client):
    r = client.get("/api/runs/2099-01-01T00-00-00Z_deadbeef/top5")
    assert r.status_code == 404
    assert "error" in r.json()["detail"]


def test_404_for_unknown_run_export(client):
    r = client.get("/api/runs/2099-01-01T00-00-00Z_deadbeef/export")
    assert r.status_code == 404


def test_404_for_unknown_run_replay(client):
    r = client.get("/api/runs/2099-01-01T00-00-00Z_deadbeef/replay")
    assert r.status_code == 404
