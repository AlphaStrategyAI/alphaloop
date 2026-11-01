#!/usr/bin/env bash
# Unpack smoke for the ad-hoc signed macOS app. No WebDriver.
#
# Uses alphaloop_*_macos_arm64.app.tar.gz, not the DMG. The DMG is a read-only
# wrapper around this same .app; mounting it adds hdiutil without changing the
# binary CI launches. Official tauri-driver cannot drive WKWebView, so this
# smoke only checks install, engine handshake, and that a normal launch does
# not open the WebDriver port. The GUI job sets ALPHALOOP_WEBDRIVER=1.
#
# Gatekeeper: Actions downloads are not browser downloads. This script still
# strips com.apple.quarantine and execs Contents/MacOS/<CFBundleExecutable>
# directly. `open` goes through LaunchServices and is more likely to stop on
# the unidentified-developer dialog. A Finder launch of a notarized-missing
# build can still be blocked; that limit is documented, and this job is not
# skipped because of it.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: macos_installed_smoke.sh <alphaloop_*_macos_arm64.app.tar.gz>" >&2
  exit 2
fi

archive=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
if [[ ! -f "$archive" ]]; then
  echo "archive missing: $archive" >&2
  exit 2
fi

repo=$(cd "$(dirname "$0")/../../.." && pwd)
shots="$repo/e2e-artifacts/screenshots"
logs="$repo/e2e-artifacts/logs"
mkdir -p "$shots" "$logs"
probe="$logs/engine-probe.txt"
: > "$probe"

log() {
  printf '%s\n' "$*" | tee -a "$probe"
}

install_root=${RUNNER_TEMP:-/tmp}/alphaloop-smoke-install
data_root=${RUNNER_TEMP:-/tmp}/alphaloop-smoke-data
rm -rf "$install_root" "$data_root"
mkdir -p "$install_root" "$data_root"

app=""
app_pid=""

stop_alphaloop() {
  if [[ -n "${app_pid}" ]]; then
    kill "$app_pid" 2>/dev/null || true
  fi
  # pkill -x clips the 16-byte comm, so match the executable basename via ps.
  python3 - <<'PY' || true
import os, signal
from pathlib import Path
own = os.getpid()
text = os.popen("ps -ax -o pid=,command=").read()
for line in text.splitlines():
    stripped = line.strip()
    if not stripped:
        continue
    pid_text, sep, command = stripped.partition(" ")
    if not sep:
        continue
    try:
        pid = int(pid_text)
    except ValueError:
        continue
    if pid == own:
        continue
    name = Path(command.strip().split(" ", 1)[0]).name
    if name in {"alphaloop", "alphaloop-engine"}:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
PY
}

redact_logs() {
  python3 - "$logs" "$shots" <<'PY'
import re, sys
from pathlib import Path
roots = [Path(sys.argv[1]), Path(sys.argv[2])]
pattern = re.compile(r'("auth_token"\s*:\s*")[^"]*"')
for root in roots:
    if not root.exists():
        continue
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".png":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        redacted = pattern.sub(r'\1[redacted]"', text)
        if redacted != text:
            path.write_text(redacted, encoding="utf-8")
PY
}

cleanup() {
  status=$?
  stop_alphaloop
  if [[ -n "$app" && -d "$app" ]]; then
    rm -rf "$app"
  fi
  rm -rf "$install_root"
  redact_logs || true
  exit "$status"
}
trap cleanup EXIT

log "archive $archive"
xattr -dr com.apple.quarantine "$archive" 2>/dev/null || true
tar -xzf "$archive" -C "$install_root"
shopt -s nullglob
apps=("$install_root"/*.app)
shopt -u nullglob
if [[ ${#apps[@]} -ne 1 ]]; then
  echo "expected one .app in $archive, found ${#apps[@]}" >&2
  exit 1
fi
app="${apps[0]}"
xattr -dr com.apple.quarantine "$app" || true
log "app $app"
# tar can drop signature metadata. Re-apply the same ad-hoc identity the build
# used (APPLE_SIGNING_IDENTITY "-"). This does not notarize the app.
if ! codesign --verify --deep --strict --verbose=2 "$app"; then
  log "codesign verify failed after untar; re-applying the ad-hoc signature"
  codesign --force --deep --sign - "$app"
  codesign --verify --deep --strict --verbose=2 "$app"
fi
exe_name=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$app/Contents/Info.plist")
binary="$app/Contents/MacOS/$exe_name"
test -x "$binary"
log "binary $binary"
engine="$app/Contents/Resources/engine/alphaloop-engine/alphaloop-engine"
test -x "$engine"
log "engine $engine"
lipo -archs "$binary" | grep -qx arm64
lipo -archs "$engine" | grep -qx arm64

stdout="$logs/engine-direct-stdout.txt"
stderr="$logs/engine-direct-stderr.txt"
: > "$stdout"
: > "$stderr"
set +e
(
  cd "$(dirname "$engine")"
  "$engine" --owner desktop >"$stdout" 2>"$stderr"
) &
direct_pid=$!
saw=0
for _ in $(seq 1 50); do
  if grep -q '"status"' "$stdout"; then
    saw=1
    break
  fi
  if ! kill -0 "$direct_pid" 2>/dev/null; then
    break
  fi
  sleep 0.3
done
kill "$direct_pid" 2>/dev/null || true
wait "$direct_pid" 2>/dev/null || true
set -e
log "direct engine handshake_json=$saw"
if [[ "$saw" -ne 1 ]]; then
  log "direct engine stdout: $(cat "$stdout" 2>/dev/null || true)"
  log "direct engine stderr: $(cat "$stderr" 2>/dev/null || true)"
  echo "direct engine probe did not print a status handshake" >&2
  exit 1
fi

unset ALPHALOOP_WEBDRIVER || true
unset TAURI_WEBDRIVER_PORT || true
export ALPHALOOP_DATA_ROOT="$data_root"
export ALPHALOOP_OFFLINE_MARKET_DATA=1
export PYTHONUNBUFFERED=1
app_log="$logs/smoke-app-stdout.log"
: > "$app_log"
"$binary" >"$app_log" 2>&1 &
app_pid=$!
log "launched pid $app_pid without ALPHALOOP_WEBDRIVER"
ready=0
for _ in $(seq 1 80); do
  if [[ -f "$data_root/desktop.log" ]] && grep -q "alphaloop-engine handshake status=ready" "$data_root/desktop.log"; then
    ready=1
    break
  fi
  if ! kill -0 "$app_pid" 2>/dev/null; then
    break
  fi
  sleep 0.4
done
if [[ "$ready" -ne 1 ]]; then
  log "desktop.log: $(cat "$data_root/desktop.log" 2>/dev/null || echo missing)"
  log "app stdout: $(cat "$app_log" 2>/dev/null || true)"
  echo "installed app did not reach engine handshake status=ready" >&2
  exit 1
fi
if ! kill -0 "$app_pid" 2>/dev/null; then
  echo "alphaloop exited before the smoke screenshot" >&2
  exit 1
fi
tty_name=$(ps -o tty= -p "$app_pid" | tr -d '[:space:]')
log "app tty ${tty_name:-empty}"
if [[ -n "$tty_name" && "$tty_name" != "??" && "$tty_name" != "?" ]]; then
  echo "app is attached to a terminal ($tty_name); launch it with a free session" >&2
  exit 1
fi
if python3 - <<'PY'
import socket, sys
try:
    sock = socket.create_connection(("127.0.0.1", 4445), 0.4)
except OSError:
    sys.exit(0)
else:
    sock.close()
    sys.exit(1)
PY
then
  log "webdriver port 4445 closed without ALPHALOOP_WEBDRIVER"
else
  echo "normal launch opened 127.0.0.1:4445; ALPHALOOP_WEBDRIVER must default off" >&2
  exit 1
fi
shot="$shots/installed-window.png"
if ! screencapture -x "$shot"; then
  echo "screencapture failed. Screen Recording may be blocked for the runner; the GUI job still takes WebView screenshots via the embedded WebDriver." >&2
  exit 1
fi
if [[ ! -s "$shot" ]]; then
  echo "screencapture wrote an empty file" >&2
  exit 1
fi
cp -f "$data_root/desktop.log" "$logs/desktop.log" 2>/dev/null || true
cp -f "$data_root/engine.log" "$logs/engine.log" 2>/dev/null || true
log "screenshot $shot"
log "engine handshake status=ready"
