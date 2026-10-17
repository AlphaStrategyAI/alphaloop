#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BIN="$ROOT/dist/alphaloop-engine/alphaloop-engine"
if [[ ! -x "$BIN" ]]; then
  echo "Run scripts/build_sidecar.sh first" >&2
  exit 1
fi

VENV="$ROOT/.venv-sidecar"
if [[ -x "$VENV/bin/python" ]]; then
  PYTHON="$VENV/bin/python"
else
  PYTHON="python3"
fi

ROOT="$ROOT" "$PYTHON" - <<'PY'
import json
import os
import subprocess
from pathlib import Path

root = Path(os.environ["ROOT"])
bin_path = root / "dist" / "alphaloop-engine" / "alphaloop-engine"
env = os.environ.copy()
env.setdefault("XDG_RUNTIME_DIR", "/tmp")
proc = subprocess.Popen(
    [str(bin_path), "--owner", "cli"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    env=env,
)
handshake = None
try:
    for _ in range(20):
        line = proc.stdout.readline().strip()
        if not line:
            continue
        if line.startswith("{"):
            handshake = json.loads(line)
            break
finally:
    proc.terminate()
    proc.wait(timeout=5)

assert handshake is not None, "no JSON handshake line from engine"
assert handshake.get("protocol_version") == 1
assert handshake.get("endpoint")
print("engine handshake ok:", handshake.get("status"))

import akshare as ak

calendar = Path(ak.__file__).resolve().parent / "file_fold" / "calendar.json"
assert calendar.is_file(), calendar
print("akshare calendar.json ok:", calendar)

bundled = (
    root / "dist" / "alphaloop-engine" / "_internal" / "akshare" / "file_fold" / "calendar.json"
)
if bundled.is_file():
    print("bundled akshare calendar ok:", bundled)
else:
    print("warn: bundled akshare calendar missing (check PyInstaller datas):", bundled)
PY

echo "smoke_sidecar: handshake + akshare calendar data verified"
