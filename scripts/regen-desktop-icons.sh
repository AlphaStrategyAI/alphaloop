#!/usr/bin/env bash
# Regenerate apps/desktop/src-tauri/icons from scripts/generate_app_icon.py (master: source-icon.svg).
# Optional: pass --tauri to also run `tauri icon` (requires Node + @tauri-apps/cli in apps/desktop).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/generate_app_icon.py

if [[ "${1:-}" == "--tauri" ]]; then
  cd apps/desktop
  npx tauri icon src-tauri/icons/icon-1024.png -o src-tauri/icons
fi

echo "Desktop icons written under apps/desktop/src-tauri/icons/"
