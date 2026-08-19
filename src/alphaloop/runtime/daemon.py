from __future__ import annotations

import errno
import http.server
import json
import logging
import os
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

from alphaloop.contracts.research_spec import ResearchSpec
from alphaloop.runtime.api import JobAPI, PreflightRejected
from alphaloop.runtime.store import JobStore
from alphaloop.runtime.supervisor import Supervisor
from alphaloop.runtime.worker import ProcessWorker

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
_LOOPBACK_HOSTS = ("127.0.0.1", "localhost")
_CONTROL_DIR = ".alphaloop"
_DAEMON_META = "daemon.json"
_DAEMON_PID = "daemon.pid"
_DAEMON_START_TIMEOUT_S = 10.0
_DAEMON_START_POLL_S = 0.05
_DAEMON_HEALTH_REQUEST_TIMEOUT_S = 0.2
logger = logging.getLogger(__name__)


class DaemonAlreadyRunning(RuntimeError):  # noqa: N818 - public API name
    pass


class UnsupportedBindHost(ValueError):  # noqa: N818 - public API name
    pass


class _ThreadingHTTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _handler_for(api: JobAPI) -> type[http.server.BaseHTTPRequestHandler]:
    class JobRequestHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/":
                self._send_text(200, "alphaloop control plane")
                return
            if path == "/healthz":
                self._send_json(200, {"status": "ok"})
                return
            prefix = "/v1/jobs/"
            if path.startswith(prefix):
                run_id = unquote(path[len(prefix) :])
                if run_id and "/" not in run_id:
                    try:
                        self._send_json(200, api.get_run(run_id))
                    except KeyError:
                        self._send_json(404, {"error": "job not found"})
                    return
            self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            if path == "/v1/jobs":
                self._create_run()
                return

            parts = path.split("/")
            if (
                len(parts) == 5
                and parts[:3] == ["", "v1", "jobs"]
                and parts[3]
                and parts[4] in ("cancel", "resume")
            ):
                self._run_action(unquote(parts[3]), parts[4])
                return
            self._send_json(404, {"error": "not found"})

        def _create_run(self) -> None:
            try:
                payload = self._read_json()
                spec = ResearchSpec.from_dict(payload)
                response = api.create_run(spec)
            except PreflightRejected as exc:
                errors = exc.args[0] if exc.args else ()
                self._send_json(400, {"errors": list(errors)})
                return
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(201, response)

        def _run_action(self, run_id: str, action: str) -> None:
            try:
                if action == "cancel":
                    response = api.cancel_run(run_id)
                else:
                    response = api.resume_run(run_id)
            except KeyError:
                self._send_json(404, {"error": "job not found"})
                return
            except ValueError as exc:
                self._send_json(409, {"error": str(exc)})
                return
            self._send_json(200, response)

        def _read_json(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            return payload

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, status: int, text: str) -> None:
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return JobRequestHandler


def start_http_server(
    api: JobAPI,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> socketserver.ThreadingTCPServer:
    if host not in _LOOPBACK_HOSTS:
        raise UnsupportedBindHost(host)
    try:
        server = _ThreadingHTTPServer((host, port), _handler_for(api))
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise DaemonAlreadyRunning(f"{host}:{port}") from exc
        raise
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _control_dir(data_dir: Path) -> Path:
    return Path(data_dir) / _CONTROL_DIR


def write_daemon_meta(data_dir: Path, host: str, port: int, pid: int) -> dict[str, Any]:
    control_dir = _control_dir(data_dir)
    control_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {"host": host, "port": port, "pid": pid}
    path = control_dir / _DAEMON_META
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    return meta


def read_daemon_meta(data_dir: Path) -> dict[str, Any]:
    path = _control_dir(data_dir) / _DAEMON_META
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("daemon metadata must be an object")
    host = payload.get("host")
    port = payload.get("port")
    pid = payload.get("pid")
    if not isinstance(host, str) or not isinstance(port, int) or not isinstance(pid, int):
        raise ValueError("invalid daemon metadata")
    return {"host": host, "port": port, "pid": pid}


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _write_pidfile(data_dir: Path, pid: int) -> Path:
    path = _control_dir(data_dir) / _DAEMON_PID
    if path.is_file():
        try:
            existing = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            existing = 0
        if _pid_is_running(existing):
            raise DaemonAlreadyRunning(f"pid {existing}")
    path.write_text(f"{pid}\n", encoding="utf-8")
    return path


def _safe_tick(supervisor: Supervisor) -> None:
    try:
        supervisor.tick()
    except Exception:
        logger.exception("supervisor tick failed")


def _supervisor_loop(supervisor: Supervisor, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        _safe_tick(supervisor)
        stop_event.wait(0.5)


def serve_forever(data_dir: Path, host: str, port: int) -> None:
    data_dir = Path(data_dir)
    control_dir = _control_dir(data_dir)
    control_dir.mkdir(parents=True, exist_ok=True)
    store = JobStore(control_dir / "state.db", data_dir)
    supervisor = Supervisor(store, data_dir, ProcessWorker())
    api = JobAPI(store, supervisor, data_dir)
    server = start_http_server(api, host, port)
    bound_host, bound_port = server.server_address[:2]
    pid = os.getpid()
    pidfile = _write_pidfile(data_dir, pid)
    meta_path = control_dir / _DAEMON_META
    write_daemon_meta(data_dir, host=bound_host, port=bound_port, pid=pid)

    stop_event = threading.Event()
    supervisor_thread = threading.Thread(
        target=_supervisor_loop,
        args=(supervisor, stop_event),
        daemon=True,
    )
    supervisor_thread.start()

    previous_handlers: dict[int, Any] = {}

    def request_stop(signum: int, frame: Any) -> None:
        stop_event.set()

    if threading.current_thread() is threading.main_thread():
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, request_stop)

    try:
        stop_event.wait()
    finally:
        stop_event.set()
        server.shutdown()
        server.server_close()
        supervisor_thread.join(timeout=1.0)
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        try:
            if read_daemon_meta(data_dir).get("pid") == pid:
                meta_path.unlink(missing_ok=True)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        try:
            if int(pidfile.read_text(encoding="utf-8").strip()) == pid:
                pidfile.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass


def _available_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


def _healthz_succeeds(host: str, port: int) -> bool:
    with urlopen(
        f"http://{host}:{port}/healthz",
        timeout=_DAEMON_HEALTH_REQUEST_TIMEOUT_S,
    ) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return isinstance(payload, dict) and payload.get("status") == "ok"


def _remove_daemon_meta_for_pid(data_dir: Path, pid: int) -> None:
    path = _control_dir(data_dir) / _DAEMON_META
    try:
        if read_daemon_meta(data_dir).get("pid") == pid:
            path.unlink(missing_ok=True)
    except (OSError, ValueError, json.JSONDecodeError):
        pass


def _stop_detached_process(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1.0)


def spawn_detached_daemon(data_dir: Path, host: str, port: int) -> dict[str, Any]:
    if host not in _LOOPBACK_HOSTS:
        raise UnsupportedBindHost(host)
    data_dir = Path(data_dir).resolve()
    selected_port = _available_port(host) if port == 0 else port
    src_dir = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(src_dir)
        if not current_pythonpath
        else os.pathsep.join((str(src_dir), current_pythonpath))
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "alphaloop.runtime.daemon",
            "--data-dir",
            str(data_dir),
            "--host",
            host,
            "--port",
            str(selected_port),
        ],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    deadline = time.monotonic() + _DAEMON_START_TIMEOUT_S
    last_error: Exception | None = None
    try:
        while time.monotonic() < deadline:
            exit_code = process.poll()
            if exit_code is not None:
                raise RuntimeError(
                    f"detached daemon exited before becoming healthy "
                    f"(exit code {exit_code})"
                )
            try:
                healthy = _healthz_succeeds(host, selected_port)
                meta = read_daemon_meta(data_dir)
                if (
                    healthy
                    and meta["port"] == selected_port
                    and meta["pid"] == process.pid
                    and process.poll() is None
                ):
                    return meta
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
            time.sleep(_DAEMON_START_POLL_S)

        detail = f": {last_error}" if last_error is not None else ""
        raise RuntimeError(
            f"detached daemon did not become healthy within "
            f"{_DAEMON_START_TIMEOUT_S:g}s{detail}"
        )
    except BaseException:
        _stop_detached_process(process)
        _remove_daemon_meta_for_pid(data_dir, process.pid)
        raise


def _create_parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m alphaloop.runtime.daemon")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    return parser


def main(argv: Any = None) -> int:
    args = _create_parser().parse_args(argv)
    serve_forever(args.data_dir, args.host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
