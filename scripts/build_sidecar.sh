#!/usr/bin/env bash
# Build PyInstaller onedir sidecar into dist/alphaloop-engine/ using a dedicated venv
# (avoids PEP 668 system-python pip failures). Requires python3-venv or ensurepip.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY_MINOR="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$(uname -s)" == "Linux" ]]; then
  PY_LIBDIR="$(python3 -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR") or "")')"
  PY_LIB="libpython${PY_MINOR}.so"
  if [[ -n "$PY_LIBDIR" ]] && [[ ! -e "$PY_LIBDIR/$PY_LIB" ]] && [[ ! -e "$PY_LIBDIR/${PY_LIB}.1.0" ]]; then
    echo "ERROR: ${PY_LIB} not found under ${PY_LIBDIR}." >&2
    echo "Install the system Python development package (e.g. python${PY_MINOR}-dev or libpython${PY_MINOR}) before building the sidecar." >&2
    exit 1
  fi
fi

VENV="$ROOT/.venv-sidecar"
VENV_PY=""
if [[ -x "$VENV/bin/python" ]]; then
  VENV_PY="$VENV/bin/python"
elif [[ -x "$VENV/Scripts/python.exe" ]]; then
  VENV_PY="$VENV/Scripts/python.exe"
fi
if [[ -z "$VENV_PY" ]]; then
  if ! python3 -m venv "$VENV" 2>/dev/null; then
    python3 -m venv --without-pip "$VENV"
    if [[ -x "$VENV/bin/python" ]]; then
      "$VENV/bin/python" -m ensurepip --upgrade
    else
      "$VENV/Scripts/python.exe" -m ensurepip --upgrade
    fi
  fi
  if [[ -x "$VENV/bin/python" ]]; then
    VENV_PY="$VENV/bin/python"
  else
    VENV_PY="$VENV/Scripts/python.exe"
  fi
fi
"$VENV_PY" -m pip install -q -U pip
"$VENV_PY" -m pip install --require-hashes -r packaging/requirements-sidecar.txt
"$VENV_PY" -m pip install --no-deps --no-build-isolation -e .
ALPHALOOP_GIT_SHA="${ALPHALOOP_GIT_SHA:-}" "$VENV_PY" "$ROOT/scripts/write_build_info.py"

"$VENV_PY" -m PyInstaller --noconfirm --clean packaging/alphaloop-engine.spec
DIST_DIR="$ROOT/dist/alphaloop-engine"
if [[ -f "$DIST_DIR/alphaloop-engine.exe" ]]; then
  ENGINE_BIN="$DIST_DIR/alphaloop-engine.exe"
else
  ENGINE_BIN="$DIST_DIR/alphaloop-engine"
fi
if [[ -x "$ENGINE_BIN" ]] && command -v ldd >/dev/null 2>&1; then
  echo "Sidecar dynamic libraries (libpython check):"
  ldd "$ENGINE_BIN" | grep -E 'libpython|not found' || true
  if ldd "$ENGINE_BIN" | grep -q 'libpython.*not found'; then
    echo "ERROR: packaged engine is missing libpython at runtime; install libpython${PY_MINOR} on target systems." >&2
    exit 1
  fi
fi
echo "PyInstaller onedir: $ROOT/dist/alphaloop-engine/"
