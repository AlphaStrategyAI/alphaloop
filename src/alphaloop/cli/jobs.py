from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError

import yaml

from alphaloop.contracts.research_spec import ResearchSpec
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

    preview = subparsers.add_parser(
        "preview",
        help="preview the compiled protocol without creating a job",
    )
    preview.add_argument("--spec", required=True, type=Path)
    preview.add_argument(
        "--json",
        action="store_true",
        help="print the preview payload as JSON",
    )
    _add_data_dir(preview)
    preview.set_defaults(func=run_preview)

    status = subparsers.add_parser("status", help="show research job status")
    status.add_argument("run_id", nargs="?")
    status.add_argument(
        "--json",
        action="store_true",
        help="print the full morning_view JSON",
    )
    _add_data_dir(status)
    status.set_defaults(func=run_status)

    cancel = subparsers.add_parser("cancel", help="cancel a research job")
    cancel.add_argument("run_id", nargs="?")
    cancel.add_argument(
        "--json",
        action="store_true",
        help="print the full morning_view JSON",
    )
    _add_data_dir(cancel)
    cancel.set_defaults(func=run_cancel)

    resume = subparsers.add_parser("resume", help="resume a research job")
    resume.add_argument("run_id", nargs="?")
    resume.add_argument(
        "--json",
        action="store_true",
        help="print the full morning_view JSON",
    )
    _add_data_dir(resume)
    resume.set_defaults(func=run_resume)

    replay = subparsers.add_parser("replay", help="rewrite report.md from sealed artifacts")
    replay.add_argument("run_id", nargs="?")
    replay.add_argument(
        "--json",
        action="store_true",
        help="print the replay verdict view as JSON",
    )
    _add_data_dir(replay)
    replay.set_defaults(func=run_replay)

    dataset = subparsers.add_parser(
        "dataset",
        help="cache a local parquet or wide close-only CSV (does not create a job)",
        description="Cache a local parquet or wide close-only CSV (does not create a job).",
    )
    dataset.add_argument(
        "path",
        type=Path,
        help="local parquet or wide close-only CSV",
    )
    dataset.add_argument(
        "--json",
        action="store_true",
        help="print dataset identity as JSON",
    )
    _add_data_dir(dataset)
    dataset.set_defaults(func=run_dataset)

    soak = subparsers.add_parser(
        "soak",
        help="print the overnight soak release checklist (does not start jobs)",
    )
    soak.add_argument(
        "--emit-plan",
        action="store_true",
        help="same as the default: print the checklist and exit",
    )
    soak.set_defaults(func=run_soak)


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


def format_protocol_preview(body: dict[str, Any]) -> str:
    from alphaloop.contracts.gates import gloss_hard_gate
    from alphaloop.protocol.dsl import gloss_signal
    from alphaloop.protocol.profiles import gloss_market_profile
    from alphaloop.runtime.morning import _format_grid_row

    gates = body.get("hard_gate_labels")
    if not gates:
        raw = body.get("hard_gates") or []
        if isinstance(raw, (list, tuple)):
            gates = [gloss_hard_gate(str(name)) for name in raw]
        else:
            gates = [gloss_hard_gate(str(raw))]
    gates_text = ", ".join(str(name) for name in gates)
    signal = body.get("signal_label") or gloss_signal(str(body.get("signal_mechanism") or ""))
    profile = body.get("market_profile_label") or gloss_market_profile(
        str(body.get("market_profile") or "")
    )
    lines: list[str] = []
    if not body.get("ok"):
        for error in body.get("errors") or []:
            lines.append(str(error))
    lines.extend(
        [
            f"planned_n_trials: {body.get('planned_n_trials', '')}",
            f"spec_id: {body.get('spec_id', '')}",
            f"statement: {body.get('statement', '')}",
            f"signal_mechanism: {signal}",
            f"market_profile: {profile}",
            f"hard_gates: {gates_text}",
            f"seed: {body.get('seed', '')}",
            f"time_budget_s: {body.get('time_budget_s', '')}",
            f"cost_budget_usd: {body.get('cost_budget_usd', '')}",
            "grid:",
        ]
    )
    for row in body.get("method_parameter_grid") or []:
        lines.append(_format_grid_row(row))
    lines.append(HOST_CONSTRAINT)
    lines.append("This preview does not claim alpha or future profitability.")
    if body.get("ok"):
        lines.append("Freeze with alphaloop submit --spec PATH")
    return "\n".join(lines) + "\n"


def _load_spec(path: Path) -> ResearchSpec | None:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("research spec must be a mapping")
        return ResearchSpec.from_dict(payload)
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        print(f"error: unable to read research spec: {exc}", file=sys.stderr)
        return None


def run_preview(args: argparse.Namespace) -> int:
    spec = _load_spec(args.spec)
    if spec is None:
        return 2
    result = _invoke(args.data_dir, lambda client: client.preview_run(spec))
    if result is None:
        return 2
    if args.json:
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("ok") else 2
    print(format_protocol_preview(result), end="")
    return 0 if result.get("ok") else 2


def _print_view(result: dict[str, Any], as_json: bool) -> int:
    from alphaloop.runtime.morning import format_status_verdict

    if as_json:
        print(json.dumps(result, sort_keys=True))
        return 0
    print(format_status_verdict(result), end="")
    return 0


def _run_action(
    args: argparse.Namespace,
    operation: Callable[[JobClient, str], dict[str, Any]],
) -> int:
    named_latest = False
    if not args.run_id:
        listed = _invoke(args.data_dir, lambda client: client.list_jobs())
        if listed is None:
            return 2
        jobs = listed.get("jobs") or []
        if not jobs:
            print("error: no overnight job yet", file=sys.stderr)
            return 2
        args.run_id = jobs[0]["run_id"]
        named_latest = not bool(getattr(args, "json", False))
    result = _invoke(
        args.data_dir,
        lambda client: operation(client, args.run_id),
    )
    if result is None:
        return 2
    if named_latest:
        print(f"run_id: {args.run_id}")
    return _print_view(result, bool(getattr(args, "json", False)))


def run_status(args: argparse.Namespace) -> int:
    from alphaloop.runtime.morning import EMPTY_STATUS_CUE

    if args.run_id:
        result = _invoke(
            args.data_dir,
            lambda client: JobClient.get_run(client, args.run_id),
        )
        if result is None:
            return 2
        return _print_view(result, args.json)

    listed = _invoke(args.data_dir, lambda client: client.list_jobs())
    if listed is None:
        return 2
    jobs = listed.get("jobs") or []
    if not jobs:
        if args.json:
            print(json.dumps({"jobs": []}, sort_keys=True))
            return 0
        print(EMPTY_STATUS_CUE, end="")
        return 0
    latest = jobs[0]
    if args.json:
        return _print_view(latest, True)
    print(f"run_id: {latest.get('run_id', '')}")
    return _print_view(latest, False)


def run_cancel(args: argparse.Namespace) -> int:
    return _run_action(args, JobClient.cancel_run)


def run_resume(args: argparse.Namespace) -> int:
    return _run_action(args, JobClient.resume_run)


def run_replay(args: argparse.Namespace) -> int:
    from alphaloop.runtime.morning import format_status_verdict
    from alphaloop.runtime.replay import rewrite_sealed_report
    from alphaloop.runtime.store import JobStore

    named_latest = False
    data_dir = Path(args.data_dir)
    if not args.run_id:
        jobs = JobStore(data_dir / ".alphaloop" / "state.db", data_dir).list_jobs()
        if not jobs:
            print("error: no overnight job yet", file=sys.stderr)
            return 2
        args.run_id = jobs[0].run_id
        named_latest = True

    try:
        view = rewrite_sealed_report(data_dir, args.run_id)
    except FileNotFoundError:
        print(
            f"error: run directory not found: {data_dir / args.run_id}",
            file=sys.stderr,
        )
        return 2
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        print(f"error: unable to read research spec: {exc}", file=sys.stderr)
        return 2
    if named_latest:
        view = {**view, "run_id": args.run_id}
    if args.json:
        print(json.dumps(view, sort_keys=True))
    else:
        if named_latest:
            print(f"run_id: {args.run_id}")
        print(format_status_verdict(view), end="")
    return 0


def run_dataset(args: argparse.Namespace) -> int:
    from alphaloop.runtime.dataset_cache import (
        DatasetRejected,
        cache_dataset_file,
        dataset_parquet_path,
        format_dataset_receipt,
    )

    path = Path(args.path)
    if not path.is_file():
        print(f"error: dataset file not found: {path}", file=sys.stderr)
        return 2
    try:
        ref = cache_dataset_file(Path(args.data_dir), path)
    except DatasetRejected as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: unable to read dataset file: {exc}", file=sys.stderr)
        return 2
    cached = dataset_parquet_path(Path(args.data_dir), ref.dataset_id)
    if args.json:
        print(
            json.dumps(
                {
                    "cached_path": str(cached),
                    "dataset_id": ref.dataset_id,
                    "sha256": ref.sha256,
                },
                sort_keys=True,
            )
        )
        return 0
    print(
        format_dataset_receipt(
            dataset_id=ref.dataset_id,
            sha256=ref.sha256,
            cached_path=str(cached),
        ),
        end="",
    )
    return 0


def run_soak(args: argparse.Namespace) -> int:
    from alphaloop.runtime.soak import emit_soak_plan

    print(emit_soak_plan(), end="")
    return 0
