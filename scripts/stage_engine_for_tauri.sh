#!/usr/bin/env bash
# Copy PyInstaller onedir into apps/desktop/src-tauri/resources for local Tauri builds.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="${1:-$ROOT/dist/alphaloop-engine}"
TAURI_ROOT="$ROOT/apps/desktop/src-tauri"
python3 "$ROOT/scripts/verify_engine_resource_layout.py" --source "$SOURCE"
python3 "$ROOT/scripts/stage_sidecar.py" --target linux --source "$SOURCE" --tauri-root "$TAURI_ROOT"
python3 "$ROOT/scripts/verify_engine_resource_layout.py" --staged "$TAURI_ROOT/resources/engine/alphaloop-engine"
