#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m pip install -q pyinstaller
python3 -m PyInstaller --noconfirm --clean packaging/alphaloop-engine.spec
echo "PyInstaller onedir: $ROOT/dist/alphaloop-engine/"
