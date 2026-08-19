from __future__ import annotations

import argparse
import asyncio
import errno
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.research_spec import ResearchSpec
from alphaloop.contracts.status import JobStatus, ResearchOutcome, derive_research_outcome
from alphaloop.runtime.checkpoint import Checkpoint, write_checkpoint, write_heartbeat

RunnerFactory = Callable[..., Any]
_WORKER_MODULE = b"alphaloop.runtime.worker"
HEARTBEAT_INTERVAL_S = 2.0


def is_worker_cmdline(raw_cmdline: bytes) -> bool:
    """True when NUL-separated argv contains ``-m`` followed by the worker module."""
    argv = raw_cmdline.split(b"\0")
    for i, arg in enumerate(argv):
        if arg == b"-m" and i + 1 < len(argv) and argv[i + 1] == _WORKER_MODULE:
            return True
    return False


def is_worker_for_run(raw_cmdline: bytes, run_id: str) -> bool:
    """True when argv identifies the worker module and an exact run ID."""
    if not is_worker_cmdline(raw_cmdline):
        return False
    argv = raw_cmdline.split(b"\0")
    expected_run_id = run_id.encode()
    for i, arg in enumerate(argv):
        if arg == b"--run-id" and i + 1 < len(argv) and argv[i + 1] == expected_run_id:
            return True
    return False


def find_running_worker_pid(run_id: str) -> Optional[int]:
    """Return a running worker PID for ``run_id``, if one exists."""
    for proc_dir in Path("/proc").glob("[0-9]*"):
        try:
            raw_cmdline = (proc_dir / "cmdline").read_bytes()
        except OSError:
            continue
        if is_worker_for_run(raw_cmdline, run_id):
            return int(proc_dir.name)
    return None


def stopgap_terminal_outcome() -> ResearchOutcome:
    return derive_research_outcome(JobStatus.COMPLETED, False, False)


def _universe(market_scope: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in market_scope.split(",") if part.strip())


def _load_or_synthesize_prices(layout: RunLayout, spec: ResearchSpec):
    import numpy as np
    import pandas as pd

    parquet = layout.run_dir / "prices.parquet"
    if parquet.is_file():
        frame = pd.read_parquet(parquet)
        prices = {str(col): frame[col].astype(float) for col in frame.columns}
        universe = _universe(spec.hypothesis.market_scope)
        primary = universe[0] if universe else next(iter(prices))
        buy_hold = prices.get(primary, next(iter(prices.values())))
        benchmark = prices.get(spec.hypothesis.benchmark, buy_hold)
        return prices, buy_hold, benchmark

    rng = np.random.default_rng(int(spec.seed))
    n = 252
    idx = pd.bdate_range("2018-01-01", periods=n)
    universe = list(_universe(spec.hypothesis.market_scope))
    assets = list(dict.fromkeys([*universe, spec.hypothesis.benchmark]))
    prices: dict[str, pd.Series] = {}
    for ticker in assets:
        shocks = rng.normal(loc=0.0003, scale=0.012, size=n)
        levels = 100.0 * np.exp(np.cumsum(shocks))
        prices[ticker] = pd.Series(levels, index=idx, dtype=float)
    primary = universe[0] if universe else assets[0]
    return prices, prices[primary], prices.get(spec.hypothesis.benchmark, prices[primary])


def _run_protocol(spec: ResearchSpec, layout: RunLayout) -> None:
    from alphaloop.protocol.loop import run_protocol

    prices, buy_hold, benchmark = _load_or_synthesize_prices(layout, spec)
    run_protocol(
        spec,
        layout,
        prices=prices,
        buy_hold_prices=buy_hold,
        benchmark_prices=benchmark,
    )


def _refresh_heartbeat(layout: RunLayout, stop: threading.Event) -> None:
    while not stop.wait(HEARTBEAT_INTERVAL_S):
        write_heartbeat(
            layout,
            pid=os.getpid(),
            at=datetime.now(timezone.utc).isoformat(),
        )


def run_worker(
    run_id: str,
    data_dir: Path,
    *,
    runner_factory: Optional[RunnerFactory] = None,
) -> int:
    data_dir = Path(data_dir)
    layout = RunLayout(data_dir / run_id)
    payload = yaml.safe_load(layout.research_spec.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("research spec must be a mapping")
    spec = ResearchSpec.from_dict(payload)

    write_heartbeat(
        layout,
        pid=os.getpid(),
        at=datetime.now(timezone.utc).isoformat(),
    )
    write_checkpoint(
        layout,
        Checkpoint(
            seq=1,
            complete=True,
            payload={
                "phase": "protocol" if runner_factory is None else "looprunner-stopgap"
            },
        ),
    )

    heartbeat_stop = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_refresh_heartbeat,
        args=(layout, heartbeat_stop),
        name=f"alphaloop-heartbeat-{run_id}",
        daemon=True,
    )
    heartbeat_thread.start()
    try:
        if runner_factory is not None:
            runner = runner_factory(
                goal=spec.hypothesis.statement,
                run_id=run_id,
                seed=spec.seed,
                budget_usd=spec.cost_budget_usd,
                timeout_s=spec.time_budget_s,
                data_dir=str(data_dir),
                dry_run=True,
            )
            asyncio.run(runner.run())
        else:
            _run_protocol(spec, layout)
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join()
    return 0


class ProcessWorker:
    def __init__(self) -> None:
        self._processes: dict[int, subprocess.Popen] = {}
        self._run_ids: dict[int, str] = {}

    def spawn(self, run_id: str, data_dir: Path) -> int:
        running_pid = find_running_worker_pid(run_id)
        if running_pid is not None:
            self._run_ids[running_pid] = run_id
            return running_pid
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "alphaloop.runtime.worker",
                "--run-id",
                run_id,
                "--data-dir",
                str(data_dir),
            ]
        )
        self._processes[process.pid] = process
        self._run_ids[process.pid] = run_id
        return process.pid

    def poll(self, pid: int, run_id: Optional[str] = None) -> Optional[int]:
        tracked_run_id = self._run_ids.get(pid)
        if (
            run_id is not None
            and tracked_run_id is not None
            and run_id != tracked_run_id
        ):
            return 1
        process = self._processes.get(pid)
        if process is None:
            expected_run_id = run_id or tracked_run_id
            if expected_run_id is None or not self._is_worker_process(
                pid, expected_run_id
            ):
                return 1
            try:
                os.kill(pid, 0)
            except OSError as exc:
                if exc.errno == errno.ESRCH:
                    return 1
                if exc.errno == errno.EPERM:
                    return None
                raise
            return None
        return process.poll()

    def terminate(self, pid: int, run_id: Optional[str] = None) -> None:
        tracked_run_id = self._run_ids.get(pid)
        if (
            run_id is not None
            and tracked_run_id is not None
            and run_id != tracked_run_id
        ):
            return
        process = self._processes.get(pid)
        if process is None:
            expected_run_id = run_id or tracked_run_id
            if expected_run_id is None or not self._is_worker_process(
                pid, expected_run_id
            ):
                return
            try:
                os.kill(pid, 15)
            except ProcessLookupError:
                pass
            return
        process.terminate()

    @staticmethod
    def _is_worker_process(pid: int, run_id: str) -> bool:
        try:
            raw_cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        except OSError:
            return False
        return is_worker_for_run(raw_cmdline, run_id)


def run_loop_command(args: argparse.Namespace) -> int:
    """Preserve the legacy ``alphaloop loop`` command implementation."""
    if args.loop_command is None:
        print("Usage: alphaloop loop {run,replay,inspect,list} ...", file=sys.stderr)
        return 1

    if args.loop_command == "list":
        data_dir = Path(args.data_dir)
        if not data_dir.is_dir():
            print(f"No runs directory at: {data_dir}", file=sys.stderr)
            return 0
        runs = sorted(p.name for p in data_dir.iterdir() if p.is_dir())
        for rid in runs:
            print(rid)
        return 0

    if args.loop_command == "replay":
        from alphaloop.loop import LoopReplay

        replay = LoopReplay(run_id=args.run_id, data_dir=args.data_dir)
        try:
            replay.validate()
        except FileNotFoundError as exc:
            print(f"Replay failed: {exc}", file=sys.stderr)
            return 1
        summary = replay.load_summary()
        print(f"run_id: {summary.run_id}")
        print(f"termination_reason: {summary.termination_reason}")
        print(f"completed/total: {summary.completed_tasks}/{summary.total_tasks}")
        print(f"top5: {len(summary.top5)} picks")
        return 0

    if args.loop_command == "inspect":
        from alphaloop.loop import LoopReplay

        replay = LoopReplay(run_id=args.run_id, data_dir=args.data_dir)
        try:
            summary = replay.load_summary()
        except FileNotFoundError as exc:
            print(f"Inspect failed: {exc}", file=sys.stderr)
            return 1
        print(f"=== {summary.run_id} ===")
        print(f"termination: {summary.termination_reason}")
        print(f"artifacts:   {summary.artifacts_dir}")
        print(f"cost:        ${summary.estimated_cost_usd:.3f}")
        print("top5:")
        for pick in summary.top5:
            thesis = pick.one_line_thesis or "(no thesis)"
            print(f"  #{pick.rank} {pick.strategy:<32} DSR={pick.dsr:.3f}  {thesis}")
        return 0

    from alphaloop.loop import LoopRunner, Planner, resolve_model

    model = resolve_model(getattr(args, "model", None))
    planner = Planner(client=None, model=model)
    runner = LoopRunner(
        goal=args.goal,
        run_id=getattr(args, "run_id", None),
        seed=getattr(args, "seed", None),
        budget_usd=getattr(args, "budget", 5.0),
        timeout_s=getattr(args, "timeout", 6 * 3600),
        target_dsr=getattr(args, "target_dsr", 1.0),
        data_dir=getattr(args, "data_dir", "./runs"),
        planner=planner,
        dry_run=bool(getattr(args, "dry_run", False)),
        git_repo_dir=getattr(args, "git_repo_dir", "."),
    )
    summary = asyncio.run(runner.run())
    print("alphaloop loop done.")
    print(f"  run_id:             {summary.run_id}")
    print(f"  termination:        {summary.termination_reason}")
    print(f"  completed/total:    {summary.completed_tasks}/{summary.total_tasks}")
    print(f"  cost (USD):         ${summary.estimated_cost_usd:.3f}")
    print(f"  elapsed (s):        {summary.elapsed_s:.2f}")
    print(f"  top5 picks:         {len(summary.top5)}")
    print(f"  artifacts dir:      {summary.artifacts_dir}")

    no_launch = bool(getattr(args, "no_launch", False))
    if not no_launch:
        try:
            from alphaloop.webui.auto_launch import auto_launch, is_headless

            if is_headless():
                print(
                    "warning: no display detected, falling back to --no-launch",
                    file=sys.stderr,
                )
            else:
                ok, url, port = auto_launch(
                    run_id=summary.run_id,
                    artifacts_dir=summary.artifacts_dir,
                )
                if ok and url:
                    print(f"alphaloop webui serving on {url}")
                    print("  (open in browser; Ctrl-C to stop)")
                elif port:
                    print(
                        f"warning: webui server started on port {port} "
                        f"but health check did not respond in 15s",
                        file=sys.stderr,
                    )
        except Exception as exc:
            print(f"warning: auto-launch failed: {exc}", file=sys.stderr)
    return 0


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m alphaloop.runtime.worker")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--data-dir", required=True, type=Path)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _create_parser().parse_args(argv)
    return run_worker(args.run_id, args.data_dir)


if __name__ == "__main__":
    sys.exit(main())
