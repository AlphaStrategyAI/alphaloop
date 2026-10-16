#!/usr/bin/env bash
# Build PyInstaller onedir sidecar into dist/alphaloop-engine/ using a dedicated venv
# (avoids PEP 668 system-python pip failures). Requires python3-venv or ensurepip.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv-sidecar"
if [[ ! -x "$VENV/bin/python" ]]; then
  if ! python3 -m venv "$VENV" 2>/dev/null; then
    python3 -m venv --without-pip "$VENV"
    "$VENV/bin/python" -m ensurepip --upgrade
  fi
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install -q -U pip
python -m pip install -q pyinstaller
python -m pip install -q -e .

python -m PyInstaller --noconfirm --clean packaging/alphaloop-engine.spec
echo "PyInstaller onedir: $ROOT/dist/alphaloop-engine/"
