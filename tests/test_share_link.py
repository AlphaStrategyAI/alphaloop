"""
Tests for the v0.7.2 R-ShareLink feature.

Covers:
* mint_token + resolve_token round-trip
* TTL expiry returns 410
* minting a new token revokes the previous one
* Token lookup returns 404 for unknown tokens
* FASTAPI endpoints POST /api/runs/<rid>/share + GET /api/share/<token>
* share_url() honors ALPHALOOP_SHARE_BASE_URL
* generate_token format (UUID4 + secrets)
"""
from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alphaloop.webui import create_app
from alphaloop.webui.share import (
    DEFAULT_TTL_DAYS,
    MAX_TTL_DAYS,
    SHARE_FILE_NAME,
    generate_token,
    list_tokens,
    mint_token,
    resolve_token,
    revoke_token,
    share_url,
)


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


@pytest.fixture
def run_id():
    return "2026-08-16T00-00-00Z_share01"


@pytest.fixture
def runs_dir(run_id):
    tmp = Path(tempfile.mkdtemp(prefix="alphaloop-share-test-"))
    run_dir = tmp / run_id
    run_dir.mkdir(parents=True)
    # minimal manifest so run_exists() returns True
    (run_dir / "manifest.yaml").write_text(
        "run_id: " + run_id + "\ngoal: test\nseed: 1\n",
        encoding="utf-8",
    )
    # minimal top5.json
    (run_dir / "top5.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "termination_reason": "B",
                "top5": [
                    {
                        "rank": i,
                        "task_id": f"task-{i:04d}",
                        "strategy": f"S{i}",
                        "factor": "M",
                        "params": {},
                        "dsr": 0.8,
                        "sharpe": 1.0,
                        "cagr": 0.1,
                        "max_dd": 0.05,
                        "passes_all": True,
                        "one_line_thesis": f"t{i}",
                    }
                    for i in range(1, 6)
                ],
            }
        ),
        encoding="utf-8",
    )
    return tmp


# ---------------------------------------------------------------------
# Token format
# ---------------------------------------------------------------------


def test_generate_token_is_hex_and_long_enough():
    t = generate_token()
    assert re.match(r"^[0-9a-f]{40}$", t), f"unexpected token format: {t}"


def test_generate_token_unique():
    tokens = {generate_token() for _ in range(100)}
    assert len(tokens) == 100


# ---------------------------------------------------------------------
# mint + resolve
# ---------------------------------------------------------------------


def test_share_mint_and_resolve(runs_dir, run_id):
    rec = mint_token(run_id=run_id, runs_dir=runs_dir)
    assert rec["run_id"] == run_id
    assert rec["token"]
    assert rec["expires_at"] > rec["created_at"]

    found = resolve_token(rec["token"], runs_dir=runs_dir)
    assert found["run_id"] == run_id
    assert found["token"] == rec["token"]


def test_share_token_not_found(runs_dir):
    with pytest.raises(KeyError):
        resolve_token("0" * 40, runs_dir=runs_dir)


def test_share_ttl_expires(runs_dir, run_id):
    """A token past its expires_at raises PermissionError."""
    rec = mint_token(run_id=run_id, runs_dir=runs_dir, ttl_days=1)
    # Tamper the expiry to be in the past.
    share_path = runs_dir / run_id / SHARE_FILE_NAME
    data = json.loads(share_path.read_text())
    for t in data["tokens"]:
        if t["token"] == rec["token"]:
            past = (
                datetime.now(timezone.utc) - timedelta(days=1)
            ).replace(microsecond=0)
            t["expires_at"] = past.isoformat().replace("+00:00", "Z")
    share_path.write_text(json.dumps(data, indent=2))

    with pytest.raises(PermissionError, match="expired"):
        resolve_token(rec["token"], runs_dir=runs_dir)


def test_share_token_rotation_revokes_previous(runs_dir, run_id):
    """A new mint should revoke the previous active token."""
    rec1 = mint_token(run_id=run_id, runs_dir=runs_dir)
    rec2 = mint_token(run_id=run_id, runs_dir=runs_dir)
    assert rec1["token"] != rec2["token"]

    # Old token should now be revoked → resolve_token raises.
    with pytest.raises(PermissionError, match="revoked"):
        resolve_token(rec1["token"], runs_dir=runs_dir)
    # New token resolves.
    found = resolve_token(rec2["token"], runs_dir=runs_dir)
    assert found["token"] == rec2["token"]


def test_share_revoke_helper(runs_dir, run_id):
    rec = mint_token(run_id=run_id, runs_dir=runs_dir)
    ok = revoke_token(rec["token"], runs_dir=runs_dir)
    assert ok is True
    with pytest.raises(PermissionError, match="revoked"):
        resolve_token(rec["token"], runs_dir=runs_dir)


def test_share_list_tokens(runs_dir, run_id):
    mint_token(run_id=run_id, runs_dir=runs_dir, ttl_days=10)
    mint_token(run_id=run_id, runs_dir=runs_dir, ttl_days=20)
    tokens = list_tokens(run_id, runs_dir=runs_dir)
    assert len(tokens) == 2
    # Older one is revoked after the second mint.
    revoked = [t for t in tokens if t.get("revoked")]
    assert len(revoked) == 1


def test_share_url_uses_env_var(monkeypatch):
    monkeypatch.setenv("ALPHALOOP_SHARE_BASE_URL", "https://example.test")
    url = share_url("abcd")
    assert url == "https://example.test/s/abcd"


def test_share_url_default_localhost():
    url = share_url("abcd", host="127.0.0.1", port=5173)
    assert url == "http://127.0.0.1:5173/s/abcd"


def test_share_ttl_clamped(runs_dir, run_id):
    """ttl_days > MAX_TTL_DAYS should be clamped to MAX_TTL_DAYS."""
    rec = mint_token(run_id=run_id, runs_dir=runs_dir, ttl_days=MAX_TTL_DAYS + 1)
    assert rec["ttl_days"] == MAX_TTL_DAYS


def test_share_mint_for_unknown_run_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        mint_token(run_id="does-not-exist", runs_dir=tmp_path)


# ---------------------------------------------------------------------
# FastAPI endpoints
# ---------------------------------------------------------------------


@pytest.fixture
def client(runs_dir):
    app = create_app(runs_dir=runs_dir)
    return TestClient(app)


def test_share_endpoint_404_for_unknown_run(runs_dir):
    app = create_app(runs_dir=runs_dir)
    c = TestClient(app)
    r = c.post("/api/runs/does-not-exist/share")
    assert r.status_code == 404


def test_share_endpoint_mint_returns_token(client, run_id):
    r = client.post(f"/api/runs/{run_id}/share?ttl_days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["url"].endswith(f"/s/{body['token']}")
    assert body["run_id"] == run_id
    assert body["ttl_days"] == 30


def test_share_endpoint_get_resolves_html(client, run_id):
    r = client.post(f"/api/runs/{run_id}/share")
    token = r.json()["token"]
    r2 = client.get(f"/api/share/{token}")
    assert r2.status_code == 200
    assert "text/html" in r2.headers["content-type"]
    body = r2.text
    assert "Shared view" in body
    assert "alphaloop" in body


def test_share_endpoint_get_404_for_unknown_token(client):
    r = client.get("/api/share/" + "0" * 40)
    assert r.status_code == 404


def test_share_endpoint_get_410_for_revoked_token(client, run_id):
    r = client.post(f"/api/runs/{run_id}/share")
    token1 = r.json()["token"]
    # Mint again → first revoke.
    r2 = client.post(f"/api/runs/{run_id}/share")
    assert r2.status_code == 200
    r3 = client.get(f"/api/share/{token1}")
    assert r3.status_code == 410


def test_share_endpoint_bad_ttl(client, run_id):
    r = client.post(f"/api/runs/{run_id}/share?ttl_days=0")
    assert r.status_code == 400
    r = client.post(f"/api/runs/{run_id}/share?ttl_days=999")
    assert r.status_code == 400
