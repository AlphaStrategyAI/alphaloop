"""
Share-link helpers for the v0.7.2 WebUI (R-ShareLink, Stories 4-7).

A share link is a UUID4 token that resolves to a read-only snapshot of
the top-5 + diagnostics for a given run. The token + run_id + expiry
live in ``runs/<rid>/.share.json`` (per-run, append-only history).

Default TTL: 90 days (per Commander's v0.7.2 default; the PRD suggested
30 days but the user can rotate/re-mint). Configurable per mint.

Per PRD §6 Open Question 2: per-run file (vs cross-run aggregation).
The PRD picks this; we follow it.
"""
from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


SHARE_FILE_NAME = ".share.json"
DEFAULT_TTL_DAYS = 90
MAX_TTL_DAYS = 365
MIN_TTL_DAYS = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    """ISO-8601 with trailing 'Z' (UTC)."""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def generate_token() -> str:
    """Return a 40-char URL-safe token (UUID4 hex + extra entropy).

    Format: a 40-char hex string. The PRD § R-ShareLink asks for an
    unguessable token. We use :func:`uuid.uuid4` for the canonical
    form (32 hex chars) and add an 8-char secrets suffix for extra
    entropy (so tokens are not guessable even if a UUID4 collision
    occurs). Total length: 40 hex chars.
    """
    return uuid.uuid4().hex + secrets.token_hex(4)


def _share_path(run_dir: Path) -> Path:
    return run_dir / SHARE_FILE_NAME


def _read_share_file(run_dir: Path) -> dict[str, Any]:
    p = _share_path(run_dir)
    if not p.exists():
        return {"tokens": []}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"tokens": []}


def _write_share_file(run_dir: Path, data: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    p = _share_path(run_dir)
    p.write_text(json.dumps(data, indent=2))


def mint_token(
    run_id: str,
    runs_dir: str | Path = "./runs",
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> dict[str, Any]:
    """Mint a new share token for ``run_id`` with the given TTL.

    Returns the dict ``{token, run_id, created_at, expires_at}`` and
    persists it to ``runs/<run_id>/.share.json``.
    """
    if ttl_days < MIN_TTL_DAYS:
        ttl_days = MIN_TTL_DAYS
    if ttl_days > MAX_TTL_DAYS:
        ttl_days = MAX_TTL_DAYS

    run_dir = Path(runs_dir) / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"run not found: {run_id}")

    token = generate_token()
    now = _utc_now()
    expiry = now + timedelta(days=ttl_days)
    record = {
        "token": token,
        "run_id": run_id,
        "created_at": _iso(now),
        "expires_at": _iso(expiry),
        "ttl_days": ttl_days,
        "revoked": False,
    }

    data = _read_share_file(run_dir)
    tokens = data.get("tokens", [])
    # Rotate: revoke any existing non-revoked tokens for this run.
    for t in tokens:
        if not t.get("revoked"):
            t["revoked"] = True
            t["revoked_at"] = _iso(now)
    tokens.append(record)
    data["tokens"] = tokens
    _write_share_file(run_dir, data)

    return record


def resolve_token(token: str, runs_dir: str | Path = "./runs") -> dict[str, Any]:
    """Look up a token across all runs.

    Returns the record dict (with ``run_id``). Raises:
      * :class:`KeyError` if not found.
      * :class:`PermissionError` if expired or revoked.
    """
    runs_root = Path(runs_dir)
    if not runs_root.exists():
        raise KeyError(f"share token not found: {token[:8]}…")

    for run_dir in sorted(runs_root.iterdir()):
        if not run_dir.is_dir():
            continue
        share_p = run_dir / SHARE_FILE_NAME
        if not share_p.exists():
            continue
        try:
            data = json.loads(share_p.read_text())
        except Exception:
            continue
        for rec in data.get("tokens", []):
            if rec.get("token") != token:
                continue
            if rec.get("revoked"):
                raise PermissionError("revoked")
            try:
                exp = datetime.fromisoformat(rec["expires_at"].replace("Z", "+00:00"))
            except Exception:
                raise PermissionError("malformed expiry")
            now = _utc_now()
            if exp <= now:
                raise PermissionError("expired")
            return rec
    raise KeyError(f"share token not found: {token[:8]}…")


def list_tokens(run_id: str, runs_dir: str | Path = "./runs") -> list[dict[str, Any]]:
    """Return all tokens (active + revoked) for a run."""
    run_dir = Path(runs_dir) / run_id
    data = _read_share_file(run_dir)
    return data.get("tokens", [])


def revoke_token(token: str, runs_dir: str | Path = "./runs") -> bool:
    """Mark a token as revoked. Returns True if found+revoked."""
    runs_root = Path(runs_dir)
    for run_dir in sorted(runs_root.iterdir()):
        if not run_dir.is_dir():
            continue
        share_p = run_dir / SHARE_FILE_NAME
        if not share_p.exists():
            continue
        try:
            data = json.loads(share_p.read_text())
        except Exception:
            continue
        changed = False
        for rec in data.get("tokens", []):
            if rec.get("token") == token and not rec.get("revoked"):
                rec["revoked"] = True
                rec["revoked_at"] = _iso(_utc_now())
                changed = True
        if changed:
            _write_share_file(run_dir, data)
            return True
    return False


def share_url(
    token: str,
    *,
    base_url: Optional[str] = None,
    host: str = "127.0.0.1",
    port: Optional[int] = None,
) -> str:
    """Build the share URL for a token.

    Honors ``$ALPHALOOP_SHARE_BASE_URL`` (per PRD § R-ShareLink), then
    falls back to ``http://<host>:<port>/s/<token>``.
    """
    import os

    base = base_url or os.environ.get("ALPHALOOP_SHARE_BASE_URL")
    if base:
        return f"{base.rstrip('/')}/s/{token}"
    if port is None:
        return f"http://{host}:5173/s/{token}"
    return f"http://{host}:{port}/s/{token}"


__all__ = [
    "SHARE_FILE_NAME",
    "DEFAULT_TTL_DAYS",
    "MAX_TTL_DAYS",
    "MIN_TTL_DAYS",
    "generate_token",
    "mint_token",
    "resolve_token",
    "list_tokens",
    "revoke_token",
    "share_url",
]
