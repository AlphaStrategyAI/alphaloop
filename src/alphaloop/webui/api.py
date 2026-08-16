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

    return app


# Default app for `uvicorn alphaloop.webui.api:app`
app = create_app()


__all__ = ["create_app", "app"]
