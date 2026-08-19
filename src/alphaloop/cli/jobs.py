from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError

import yaml

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import evidence_from_dict, outcome_from_evidence
from alphaloop.contracts.research_spec import ResearchSpec
from alphaloop.contracts.status import JobStatus, ResearchOutcome
from alphaloop.runtime.client import JobClient
from alphaloop.runtime.daemon import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    read_daemon_meta,
    serve_forever,
    spawn_detached_daemon,
)
from alphaloop.runtime.preflight import HOST_CONSTRAINT

DEFAULT_DATA_DIR = "./runs"


def _add_data_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        type=Path,
        help="runs/ output root",
    )


def register(subparsers: argparse._SubParsersAction) -> None:
    start = subparsers.add_parser("start", help="start the local alphaloop daemon")
    _add_data_dir(start)
    start.add_argument("--host", default=DEFAULT_HOST)
    start.add_argument("--port", type=int, default=DEFAULT_PORT)
    start.add_argument("--detach", action="store_true")
    start.set_defaults(func=run_start)

    submit = subparsers.add_parser("submit", help="submit a research job")
    submit.add_argument("--spec", required=True, type=Path)
    _add_data_dir(submit)
    submit.set_defaults(func=run_submit)

    status = subparsers.add_parser("status", help="show research job status")
    status.add_argument("run_id")
    _add_data_dir(status)
    status.set_defaults(func=run_status)

    cancel = subparsers.add_parser("cancel", help="cancel a research job")
    cancel.add_argument("run_id")
    _add_data_dir(cancel)
    cancel.set_defaults(func=run_cancel)

    resume = subparsers.add_parser("resume", help="resume a research job")
    resume.add_argument("run_id")
    _add_data_dir(resume)
    resume.set_defaults(func=run_resume)

    replay = subparsers.add_parser("replay", help="rewrite report.md from sealed artifacts")
    replay.add_argument("run_id")
    _add_data_dir(replay)
    replay.set_defaults(func=run_replay)


def _daemon_unavailable(exc: Exception) -> int:
    print(
        f"error: alphaloop daemon is unavailable ({exc}); run `alphaloop start`",
        file=sys.stderr,
    )
    return 2


def _http_error(exc: HTTPError) -> int:
    body = exc.read().decode("utf-8", errors="replace").strip()
    detail = f": {body}" if body else ""
    print(
        f"error: daemon request failed (HTTP {exc.code} {exc.reason}){detail}",
        file=sys.stderr,
    )
    return 2


def _daemon_request_failed(exc: Exception) -> int:
    print(f"error: daemon request failed ({exc})", file=sys.stderr)
    return 2


def _connect(data_dir: Path) -> JobClient:
    meta = read_daemon_meta(data_dir)
    client = JobClient(f"http://{meta['host']}:{meta['port']}")
    client.healthz()
    return client


def _invoke(data_dir: Path, operation: Callable[[JobClient], dict[str, Any]]) -> Any:
    try:
        return operation(_connect(data_dir))
    except HTTPError as exc:
        _http_error(exc)
        return None
    except (FileNotFoundError, URLError) as exc:
        _daemon_unavailable(exc)
        return None
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        _daemon_request_failed(exc)
        return None


def run_start(args: argparse.Namespace) -> int:
    if args.detach:
        meta = spawn_detached_daemon(args.data_dir, args.host, args.port)
        print(f"host: {meta['host']}")
        print(f"port: {meta['port']}")
        print(f"pid: {meta['pid']}")
        return 0
    serve_forever(args.data_dir, args.host, args.port)
    return 0


def run_submit(args: argparse.Namespace) -> int:
    try:
        payload = yaml.safe_load(args.spec.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("research spec must be a mapping")
        spec = ResearchSpec.from_dict(payload)
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        print(f"error: unable to read research spec: {exc}", file=sys.stderr)
        return 2

    result = _invoke(args.data_dir, lambda client: client.create_run(spec))
    if result is None:
        return 2
    print(f"run_id: {result['run_id']}")
    print(HOST_CONSTRAINT)
    return 0


def _run_action(
    args: argparse.Namespace,
    operation: Callable[[JobClient, str], dict[str, Any]],
) -> int:
    result = _invoke(
        args.data_dir,
        lambda client: operation(client, args.run_id),
    )
    if result is None:
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


def run_status(args: argparse.Namespace) -> int:
    return _run_action(args, JobClient.get_run)


def run_cancel(args: argparse.Namespace) -> int:
    return _run_action(args, JobClient.cancel_run)


def run_resume(args: argparse.Namespace) -> int:
    return _run_action(args, JobClient.resume_run)


def run_replay(args: argparse.Namespace) -> int:
    from alphaloop.runtime.artifacts_io import write_report
    from alphaloop.runtime.morning import (
        STOP_REASON_ALL_GATES_PASSED,
        STOP_REASON_HARD_GATE_FAILED,
        STOP_REASON_INCOMPLETE_EVIDENCE,
    )

    layout = RunLayout(Path(args.data_dir) / args.run_id)
    if not layout.run_dir.is_dir():
        print(f"error: run directory not found: {layout.run_dir}", file=sys.stderr)
        return 2

    spec = None
    spec_path = layout.research_spec
    if spec_path.is_file():
        try:
            payload = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("research spec must be a mapping")
            spec = ResearchSpec.from_dict(payload)
        except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
            print(f"error: unable to read research spec: {exc}", file=sys.stderr)
            return 2

    gates_path = layout.evidence / "gates.json"
    outcome = ResearchOutcome.INCONCLUSIVE
    if gates_path.is_file():
        try:
            payload = json.loads(gates_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                evidence = evidence_from_dict(payload)
                if evidence.complete:
                    outcome = outcome_from_evidence(JobStatus.COMPLETED, evidence)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass

    if outcome is ResearchOutcome.FOUND:
        stop_reason = STOP_REASON_ALL_GATES_PASSED
    elif outcome is ResearchOutcome.NO_EVIDENCE:
        stop_reason = STOP_REASON_HARD_GATE_FAILED
    elif outcome is ResearchOutcome.INCONCLUSIVE:
        stop_reason = STOP_REASON_INCOMPLETE_EVIDENCE
    else:
        stop_reason = None

    write_report(
        layout,
        research_outcome=outcome.value,
        stop_reason=stop_reason,
        spec=spec,
    )
    print(f"research_outcome: {outcome.value}")
    return 0
