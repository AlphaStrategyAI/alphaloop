#!/usr/bin/env bash
# Install a built .deb in a clean Ubuntu container, then ldd and start the engine.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: smoke_installed_deb.sh <deb> <image>" >&2
  exit 2
fi
DEB="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
IMAGE="$2"
NAME="$(basename "$DEB")"

docker run --rm -v "$(dirname "$DEB")":/artifacts:ro "$IMAGE" bash -s -- "$NAME" <<'EOS'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y file "/artifacts/$1"
pkg="$(dpkg-deb -f "/artifacts/$1" Package)"
mapfile -t files < <(dpkg -L "$pkg")
engine=""
app=""
for path in "${files[@]}"; do
  if [[ -f "$path" && "$(basename "$path")" == "alphaloop-engine" ]]; then
    engine="$path"
  fi
done
for path in "${files[@]}"; do
  if [[ -x "$path" && -f "$path" && "$path" != "$engine" && "$(basename "$path")" != "alphaloop-engine" ]]; then
    case "$path" in
      *.so|*.so.*) continue ;;
    esac
    if file "$path" | grep -q 'ELF'; then
      app="$path"
      break
    fi
  fi
done
if [[ -z "$app" || -z "$engine" ]]; then
  echo "could not find the app or engine in package $pkg" >&2
  printf '%s\n' "${files[@]}" >&2
  exit 1
fi
echo "app $app"
echo "engine $engine"
ldd "$app"
ldd "$engine"
if ldd "$app" | grep -q 'not found'; then
  echo "app is missing a shared library" >&2
  exit 1
fi
missing="$(ldd "$engine" | grep 'not found' || true)"
if [[ -n "$missing" ]]; then
  internal="$(dirname "$engine")/_internal"
  if [[ -d "$internal" ]] && ! echo "$missing" | grep -v libpython | grep -q 'not found'; then
    echo "engine records libpython; PyInstaller _internal is next to the binary"
  else
    echo "engine is missing a shared library" >&2
    echo "$missing" >&2
    exit 1
  fi
fi
mkdir -p /tmp/al-data /tmp/al-rt
export ALPHALOOP_DATA_ROOT=/tmp/al-data
export ALPHALOOP_RUNTIME_ROOT=/tmp/al-rt
: > /tmp/handshake.txt
"$engine" --owner desktop > /tmp/handshake.txt 2>/tmp/engine.err &
child=$!
for _ in $(seq 1 40); do
  if grep -q '"status"' /tmp/handshake.txt; then
    kill "$child" >/dev/null 2>&1 || true
    wait "$child" >/dev/null 2>&1 || true
    echo "engine handshake: $(head -1 /tmp/handshake.txt)"
    exit 0
  fi
  if ! kill -0 "$child" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
echo "engine did not report ready" >&2
cat /tmp/handshake.txt /tmp/engine.err >&2 || true
kill "$child" >/dev/null 2>&1 || true
exit 1
EOS
