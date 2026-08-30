import argparse
import io
import json
import multiprocessing
from datetime import UTC, datetime
from pathlib import Path

from apps.cli.main import Launcher, build_parser, get_status, run
from engine.research.runtime import EngineLock, RuntimePaths
from engine.research.store import SQLiteStore

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def paths(root: Path) -> RuntimePaths:
    return RuntimePaths(root, root / "engine.lock", root / "owner.json")


class HoldingLauncher(Launcher):
    def __init__(self, paths: RuntimePaths) -> None:
        self.paths = paths
        self.calls = 0
        self.lock: EngineLock | None = None

    def start(self, owner: str) -> None:
        self.calls += 1
        self.lock = EngineLock.acquire(self.paths, "cli")
        SQLiteStore(self.paths.database_file).heartbeat(self.lock.owner, NOW)


def parser_commands(parser: argparse.ArgumentParser) -> set[str]:
    action = next(
        item
        for item in parser._actions
        if isinstance(item, argparse._SubParsersAction)
    )
    return set(action.choices)


def test_cli_surface_is_exactly_start_and_status() -> None:
    assert parser_commands(build_parser()) == {"start", "status"}


def test_status_reports_stopped_with_stable_json(tmp_path: Path) -> None:
    result = get_status(paths(tmp_path))
    assert result.running is False
    assert result.owner is None
    assert result.pid is None
    assert result.has_running_research is False
    assert result.awaiting_confirm is False


def test_start_is_idempotent_and_status_redacts_runtime_secrets(tmp_path: Path) -> None:
    runtime = paths(tmp_path)
    launcher = HoldingLauncher(runtime)
    output = io.StringIO()

    assert run(["start"], runtime, launcher, output) == 0
    assert run(["start"], runtime, launcher, output) == 0

    lines = [json.loads(line) for line in output.getvalue().splitlines()]
    assert launcher.calls == 1
    assert lines[-1]["running"] is True
    assert lines[-1]["owner"] == "cli"
    assert "endpoint" not in lines[-1]
    assert "auth_token" not in lines[-1]
    assert launcher.lock is not None
    launcher.lock.close()


def test_cli_start_does_not_replace_desktop_owner(tmp_path: Path) -> None:
    runtime = paths(tmp_path)
    desktop = EngineLock.acquire(runtime, "desktop")
    launcher = HoldingLauncher(runtime)
    output = io.StringIO()

    assert run(["start"], runtime, launcher, output) == 0
    assert launcher.calls == 0
    assert json.loads(output.getvalue())["owner"] == "desktop"
    desktop.close()


def contend(root: str, queue: multiprocessing.Queue) -> None:
    runtime = paths(Path(root))
    try:
        lock = EngineLock.acquire(runtime, "cli")
    except RuntimeError:
        queue.put(False)
    else:
        queue.put(True)
        import time
        time.sleep(0.3)
        lock.close()


def test_two_processes_cannot_own_the_engine_together(tmp_path: Path) -> None:
    queue: multiprocessing.Queue = multiprocessing.Queue()
    first = multiprocessing.Process(target=contend, args=(str(tmp_path), queue))
    second = multiprocessing.Process(target=contend, args=(str(tmp_path), queue))
    first.start()
    second.start()
    first.join()
    second.join()
    assert sorted([queue.get(), queue.get()]) == [False, True]
