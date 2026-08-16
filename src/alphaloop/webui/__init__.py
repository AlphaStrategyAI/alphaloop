"""
alphaloop.webui — FastAPI JSON-only backend for the v0.7.1 WebUI.

This module exposes the v0.7 loop artifacts (manifest.yaml, top5.json,
results.parquet, report.md) as JSON over HTTP. The frontend (Vite + React
SPA) consumes these endpoints; FastAPI does NOT render HTML.

Endpoints (all under /api/, JSON only):

  GET /api/runs                              → list_runs
  GET /api/runs/{rid}/top5                   → top5
  GET /api/runs/{rid}/strategies/{sid}       → strategy_detail
  GET /api/runs/{rid}/diagnostics            → diagnostics (radar + bar)
  GET /api/runs/{rid}/replay                 → 6-node DAG + timing
  GET /api/runs/{rid}/stream                 → SSE live progress
  GET /api/runs/{rid}/export                 → standalone HTML
  GET /healthz                                → smoke

See docs/design/v071-webui.md § 3.1 for the full schema.
"""
from __future__ import annotations

from .api import create_app

__all__ = ["create_app"]
