from __future__ import annotations

import errno
import http.server
import json
import socketserver
import threading
from typing import Any
from urllib.parse import unquote, urlsplit

from alphaloop.contracts.research_spec import ResearchSpec
from alphaloop.runtime.api import JobAPI, PreflightRejected

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
_LOOPBACK_HOSTS = ("127.0.0.1", "localhost")


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
