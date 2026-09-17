from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, TextIO

from engine.research.runtime import (
    OwnerKind,
    RuntimePaths,
    read_live_owner,
)
from engine.research.store import SQLiteStore


@dataclass(frozen=True, slots=True)
class EngineStatus:
    running: bool
    owner: OwnerKind | None
    pid: int | None
    has_running_research: bool
    awaiting_confirm: bool


class Launcher(Protocol):
    def start(self, owner: str) -> None:
        raise NotImplementedError


class DetachedLauncher:
    def __init__(self, paths: RuntimePaths) -> None:
        self.paths = paths

    @staticmethod
    def _command() -> list[str]:
        suffix = ".exe" if os.name == "nt" else ""
        sibling = Path(sys.executable).with_name(f"alphaloop-engine{suffix}")
        if getattr(sys, "frozen", False) and sibling.is_file():
            return [str(sibling)]
        return [sys.executable, "-m", "engine.main"]

    def start(self, owner: str) -> None:
        self.paths.root.mkdir(parents=True, exist_ok=True)
        log = open(self.paths.engine_log, "ab", buffering=0)  # noqa: SIM115
        kwargs: dict[str, object] = {
            "stdin": subprocess.DEVNULL,
            "stdout": log,
            "stderr": log,
            "close_fds": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
                | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
                | subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            )
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(self._command() + ["--owner", owner], **kwargs)  # type: ignore[call-overload]
        log.close()
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            record = read_live_owner(self.paths)
            if (
                record is not None
                and record.phase == "ready"
                and record.endpoint
                and record.auth_token
            ):
                return
            time.sleep(0.05)
        process.terminate()
        process.wait(timeout=5.0)
        raise TimeoutError("alphaloop engine did not publish readiness within 10 seconds")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alphaloop")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("start", help="start or reuse the headless engine")
    commands.add_parser("status", help="show engine and research status")
    return parser


def get_status(paths: RuntimePaths) -> EngineStatus:
    owner = read_live_owner(paths)
    if owner is None:
        return EngineStatus(False, None, None, False, False)
    store = SQLiteStore(paths.database_file)
    running, awaiting = store.status_flags()
    return EngineStatus(True, owner.owner, owner.pid, running, awaiting)


def _public(status: EngineStatus) -> dict[str, object]:
    return asdict(status)


def run(
    argv: Sequence[str],
    paths: RuntimePaths,
    launcher: Launcher,
    output: TextIO,
) -> int:
    command = build_parser().parse_args(argv).command
    if command == "start" and read_live_owner(paths) is None:
        launcher.start("cli")
    status = get_status(paths)
    output.write(json.dumps(_public(status), sort_keys=True) + "\n")
    return 0


def main() -> int:
    paths = RuntimePaths.default()
    return run(sys.argv[1:], paths, DetachedLauncher(paths), sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
