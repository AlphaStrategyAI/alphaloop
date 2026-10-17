#!/usr/bin/env bash
# Copy PyInstaller onedir into apps/desktop/src-tauri/resources for local Tauri builds.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="${1:-$ROOT/dist/alphaloop-engine}"
TAURI_ROOT="$ROOT/apps/desktop/src-tauri"
python3 "$ROOT/scripts/verify_engine_resource_layout.py" --source "$SOURCE"
if [ -z "${TARGET:-}" ]; then
  case "$(uname -s)" in
    Darwin) TARGET=macos ;;
    MINGW*|MSYS*|CYGWIN*) TARGET=windows ;;
    *) TARGET=linux ;;
  esac
fi
python3 "$ROOT/scripts/stage_sidecar.py" --target "$TARGET" --source "$SOURCE" --tauri-root "$TAURI_ROOT"
python3 "$ROOT/scripts/verify_engine_resource_layout.py" --staged "$TAURI_ROOT/resources/engine/alphaloop-engine"
