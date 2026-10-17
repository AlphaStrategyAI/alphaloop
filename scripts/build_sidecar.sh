#!/usr/bin/env bash
# Build PyInstaller onedir sidecar into dist/alphaloop-engine/ using a dedicated venv
# (avoids PEP 668 system-python pip failures). Requires python3-venv or ensurepip.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY_MINOR="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_LIBDIR="$(python3 -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR") or "")')"
PY_LIB="libpython${PY_MINOR}.so"
if [[ -n "$PY_LIBDIR" ]] && [[ ! -e "$PY_LIBDIR/$PY_LIB" ]] && [[ ! -e "$PY_LIBDIR/${PY_LIB}.1.0" ]]; then
  echo "ERROR: ${PY_LIB} not found under ${PY_LIBDIR}." >&2
  echo "Install the system Python development package (e.g. python${PY_MINOR}-dev or libpython${PY_MINOR}) before building the sidecar." >&2
  exit 1
fi

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
ENGINE_BIN="$ROOT/dist/alphaloop-engine/alphaloop-engine"
if [[ -x "$ENGINE_BIN" ]] && command -v ldd >/dev/null 2>&1; then
  echo "Sidecar dynamic libraries (libpython check):"
  ldd "$ENGINE_BIN" | grep -E 'libpython|not found' || true
  if ldd "$ENGINE_BIN" | grep -q 'libpython.*not found'; then
    echo "ERROR: packaged engine is missing libpython at runtime; install libpython${PY_MINOR} on target systems." >&2
    exit 1
  fi
fi
echo "PyInstaller onedir: $ROOT/dist/alphaloop-engine/"
