"""
Auto-launch helper for the v0.7.2 WebUI.

When `alphaloop loop` finishes successfully, the user wants their browser
to open to the top-5 view automatically (R-AutoLaunch, Story 1). This
module encapsulates the side-effecting parts so the CLI stays thin and
the behavior is unit-testable.

Behavior matrix (per v0.7.2 PRD § R-AutoLaunch):

* :func:`pick_free_port` — probe 5173..5183, fall back to OS-assigned
  ephemeral. Returns the chosen port.
* :func:`is_headless` — best-effort heuristic: no ``$DISPLAY`` (Linux),
  no ``$SSH_TTY``, and ``sys.platform == "linux"`` without a tty.
* :func:`spawn_webui_server` — fork a child process running the FastAPI
  app via uvicorn. Registers an atexit hook so the child dies when the
  CLI exits.
* :func:`open_in_browser` — wrap :func:`webbrowser.open` with a headless
  check. Honors the ``$BROWSER`` env var.
* :func:`auto_launch` — orchestrate: pick port, start server, write
  ``.webui-port`` artifact, open browser. Returns the URL.
"""
from __future__ import annotations

import atexit
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Optional, Tuple


DEFAULT_PORT_START = 5173
DEFAULT_PORT_END = 5183
DEFAULT_HOST = "127.0.0.1"


def pick_free_port(
    host: str = DEFAULT_HOST,
    start: int = DEFAULT_PORT_START,
    end: int = DEFAULT_PORT_END,
) -> int:
    """Return a free TCP port on ``host``.

    Tries ``start..end`` inclusive. If all bound, falls back to an
    OS-assigned ephemeral port. The probe socket is closed before
    returning so the port is (briefly) reusable; the caller should
    bind again or hand the port to uvicorn for a real listen.
    """
    for port in range(start, end + 1):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            s.close()
            return port
        except OSError:
            s.close()
            continue
    # Fall back: OS-assigned ephemeral port.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, 0))
    _, port = s.getsockname()
    s.close()
    return int(port)


def is_headless() -> bool:
    """Best-effort: return True if no display is detected.

    On macOS / Windows, always False (the OS handles headless inside
    ``webbrowser``, which fails silently or raises). On Linux we check
    ``$DISPLAY`` (X11) and ``$WAYLAND_DISPLAY`` (Wayland). ``$SSH_TTY``
    alone is not enough — many users run loops over SSH with a
    forwarded display.
    """
    if sys.platform != "linux":
        return False
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return False
    return True


def _wait_for_http(url: str, timeout_s: float = 15.0, interval_s: float = 0.5) -> bool:
    """Poll ``url`` until it returns 200/204 or the timeout elapses."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status in (200, 204):
                    return True
        except Exception:
            time.sleep(interval_s)
    return False


def spawn_webui_server(
    host: str = DEFAULT_HOST,
    port: int = 5173,
    runs_dir: str = "./runs",
    log_path: Optional[Path] = None,
) -> subprocess.Popen:
    """Spawn ``uvicorn alphaloop.webui.api:app`` as a child process.

    Registers an :func:`atexit` hook so the child is terminated when
    the CLI exits. The child writes its stdout/stderr to ``log_path``
    (or DEVNULL if unspecified) so the CLI's own stdout stays clean.
    """
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "alphaloop.webui.api:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_fh = open(log_path, "ab")
    else:
        log_fh = subprocess.DEVNULL

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=log_fh,
        stderr=log_fh,
        env=env,
        cwd=os.getcwd(),
    )

    def _cleanup() -> None:
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    atexit.register(_cleanup)
    return proc


def open_in_browser(url: str) -> bool:
    """Open ``url`` in the user's default browser. Returns True if ok."""
    try:
        return bool(webbrowser.open(url, new=2))
    except Exception:
        return False


def write_port_artifact(run_dir: Path, port: int) -> Path:
    """Write ``.webui-port`` under ``run_dir`` so future calls can
    resolve the port without re-scanning.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    p = run_dir / ".webui-port"
    p.write_text(f"{port}\n")
    return p


def auto_launch(
    run_id: str,
    artifacts_dir: str,
    *,
    no_launch: bool = False,
    host: str = DEFAULT_HOST,
    port_start: int = DEFAULT_PORT_START,
    port_end: int = DEFAULT_PORT_END,
    open_browser: bool = True,
) -> Tuple[bool, Optional[str], Optional[int]]:
    """High-level: spawn the WebUI server and open the browser.

    Returns (ok, url, port). If ``no_launch`` is True, returns
    (False, None, None) without spawning anything. If headless and
    ``open_browser`` is True, the server is still started but the
    browser is not opened (the URL is returned for the caller to print).
    """
    if no_launch:
        return (False, None, None)

    port = pick_free_port(host=host, start=port_start, end=port_end)
    server_log = Path(artifacts_dir) / ".webui-server.log"
    spawn_webui_server(
        host=host, port=port, runs_dir="./runs", log_path=server_log
    )

    # Wait for the FastAPI server to come up.
    health_url = f"http://{host}:{port}/healthz"
    ready = _wait_for_http(health_url, timeout_s=15.0)
    if not ready:
        # Don't open the browser; the server may still be starting.
        return (False, None, port)

    url = f"http://{host}:{port}/run/{run_id}"
    write_port_artifact(Path(artifacts_dir), port)

    if open_browser and not is_headless():
        # Defensive: even if the orchestrator's open_in_browser mock
        # raises (e.g. test stub), the loop must not crash.
        try:
            open_in_browser(url)
        except Exception:
            pass
    return (True, url, port)


__all__ = [
    "DEFAULT_PORT_START",
    "DEFAULT_PORT_END",
    "DEFAULT_HOST",
    "pick_free_port",
    "is_headless",
    "spawn_webui_server",
    "open_in_browser",
    "write_port_artifact",
    "auto_launch",
]
