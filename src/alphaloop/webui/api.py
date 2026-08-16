"""
FastAPI app factory for the v0.7.1 WebUI JSON backend.

Exposes 7 JSON endpoints + /healthz. The frontend (Vite + React SPA)
at :5173 fetches from these endpoints via the vite proxy.

Usage:
    uvicorn alphaloop.webui.api:app --reload --port 8000
    # or programmatically:
    from alphaloop.webui import create_app
    app = create_app(runs_dir="./runs")
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

from .data import ArtifactReader
from .export import build_export_html
from .share import (
    DEFAULT_TTL_DAYS,
    MAX_TTL_DAYS,
    mint_token,
    resolve_token,
    share_url,
)
from .sse import stream_run


def create_app(runs_dir: Path | str = "./runs") -> FastAPI:
    """Build a FastAPI app bound to ``runs_dir``."""
    app = FastAPI(
        title="alphaloop WebUI API",
        description="JSON-only backend for the v0.7.1 WebUI (Vite + React SPA).",
        version="0.7.1",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    reader = ArtifactReader(runs_dir)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {
            "status": "ok",
            "runs_dir": str(runs_dir),
            "n_runs": len(reader.list_runs()),
        }

    @app.get("/api/runs")
    async def list_runs() -> dict:
        return {"runs": reader.list_runs()}

    @app.get("/api/runs/{rid}/top5")
    async def top5(rid: str) -> dict:
        if not reader.run_exists(rid):
            raise HTTPException(status_code=404, detail={"error": f"run not found: {rid}"})
        return reader.top5_response(rid)

    @app.get("/api/runs/{rid}/strategies/{sid}")
    async def strategy_detail(rid: str, sid: str) -> dict:
        if not reader.run_exists(rid):
            raise HTTPException(status_code=404, detail={"error": f"run not found: {rid}"})
        return reader.strategy_detail_response(rid, sid)

    @app.get("/api/runs/{rid}/diagnostics")
    async def diagnostics(
        rid: str,
        compare: Optional[str] = Query(default=None),
    ) -> dict:
        if not reader.run_exists(rid):
            raise HTTPException(status_code=404, detail={"error": f"run not found: {rid}"})
        return reader.diagnostics_response(rid, compare=compare)

    @app.get("/api/runs/{rid}/replay")
    async def replay(rid: str) -> dict:
        if not reader.run_exists(rid):
            raise HTTPException(status_code=404, detail={"error": f"run not found: {rid}"})
        return reader.replay_response(rid)

    @app.get("/api/runs/{rid}/stream")
    async def stream(rid: str) -> StreamingResponse:
        if not reader.run_exists(rid):
            raise HTTPException(status_code=404, detail={"error": f"run not found: {rid}"})

        async def event_generator():
            async for ev in stream_run(Path(runs_dir) / rid):
                if ev.get("event") == "comment":
                    yield f": {ev['data']}\n\n"
                else:
                    yield f"event: {ev['event']}\ndata: {ev['data']}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/runs/{rid}/export")
    async def export_html(rid: str) -> HTMLResponse:
        if not reader.run_exists(rid):
            raise HTTPException(status_code=404, detail={"error": f"run not found: {rid}"})
        top5_payload = reader.top5_response(rid)
        diag_payload = reader.diagnostics_response(rid)
        html = build_export_html(rid, top5_payload, diag_payload)
        return HTMLResponse(
            content=html,
            headers={
                "Content-Disposition": f'attachment; filename="alphaloop-{rid}.html"',
            },
        )

    # --- v0.7.2: Share link (R-ShareLink stories 4-7) ---
    #
    # The share-link endpoint is intentionally **read-only** on the
    # GET side: a viewer of a shared URL can see the top-5 + diagnostics
    # but cannot rerun, edit, or delete. The token is a UUID4 + secrets
    # suffix (40 hex chars); resolution is O(N_runs * N_tokens) which
    # is fine for thousands of runs.

    @app.post("/api/runs/{rid}/share")
    async def create_share(
        rid: str,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> dict:
        if not reader.run_exists(rid):
            raise HTTPException(
                status_code=404, detail={"error": f"run not found: {rid}"}
            )
        if ttl_days < 1 or ttl_days > MAX_TTL_DAYS:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"ttl_days must be 1..{MAX_TTL_DAYS} (got {ttl_days})"
                },
            )
        rec = mint_token(
            run_id=rid, runs_dir=runs_dir, ttl_days=ttl_days
        )
        url = share_url(rec["token"])
        return {
            "token": rec["token"],
            "url": url,
            "created_at": rec["created_at"],
            "expires_at": rec["expires_at"],
            "ttl_days": rec["ttl_days"],
            "run_id": rid,
        }

    @app.get("/api/share/{token}")
    async def get_share(token: str) -> HTMLResponse:
        try:
            rec = resolve_token(token, runs_dir=runs_dir)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail={"error": "share link not found"},
            )
        except PermissionError as e:
            # Expired or revoked.
            raise HTTPException(
                status_code=410,
                detail={"error": f"share link {str(e)}"},
            )
        rid = rec["run_id"]
        top5_payload = reader.top5_response(rid)
        diag_payload = reader.diagnostics_response(rid)
        html = build_share_html(rid, top5_payload, diag_payload, rec)
        return HTMLResponse(content=html)

    return app


def build_share_html(
    rid: str,
    top5_payload: dict,
    diagnostics_payload: dict,
    share_record: dict,
) -> str:
    """Wrap the v0.7.1 export HTML with a read-only banner.

    Reuses :func:`build_export_html` so the visual is identical to
    ``/api/runs/<rid>/export``; the only addition is a small banner
    that disclaims the read-only nature and shows the expiry.
    """
    base = build_export_html(rid, top5_payload, diagnostics_payload)
    expires = share_record.get("expires_at", "")
    banner = (
        f'<div style="background:rgba(91,108,255,0.15);'
        f'border:1px solid #5b6cff;border-radius:8px;'
        f'padding:12px 16px;margin-bottom:24px;'
        f'color:#e5e9f0;font-size:13px;">'
        f'<strong>Shared view — read only.</strong> '
        f'Generated by alphaloop v0.7.2. '
        f'Link expires {expires}. '
        f'No rerun, edit, or share-of-share buttons.'
        f'</div>'
    )
    # Insert the banner right after <body>.
    return base.replace("<body>", f"<body>\n  {banner}", 1)


# Default app for `uvicorn alphaloop.webui.api:app`
app = create_app()


__all__ = ["create_app", "app"]
