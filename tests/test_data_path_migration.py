from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from engine.research.data_paths import resolve_data_root
from engine.research.path_migration import MIGRATION_MARKER, migrate_legacy_runtime_data
from engine.research.runtime import EnginePaths


def test_migrate_copies_legacy_db_and_writes_marker(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    data = tmp_path / "data"
    runtime.mkdir()
    legacy_db = runtime / "research.db"
    with sqlite3.connect(legacy_db) as conn:
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()

    assert migrate_legacy_runtime_data(runtime, data) is True
    assert (data / "research.db").is_file()
    assert (data / MIGRATION_MARKER).is_file()
    assert legacy_db.is_file()


def test_migrate_skips_when_data_db_already_exists(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    data = tmp_path / "data"
    runtime.mkdir()
    data.mkdir()
    (runtime / "research.db").write_bytes(b"legacy")
    (data / "research.db").write_bytes(b"current")
    assert migrate_legacy_runtime_data(runtime, data) is False


def test_engine_paths_default_runs_migration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime = tmp_path / "rt"
    data = tmp_path / "data"
    runtime.mkdir()
    (runtime / "research.db").write_bytes(b"sqlite")
    monkeypatch.setenv("ALPHALOOP_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("ALPHALOOP_DATA_ROOT", str(data))
    paths = EnginePaths.default()
    assert paths.data.database_file.read_bytes() == b"sqlite"
    assert (data / MIGRATION_MARKER).exists()


def test_resolve_data_root_honours_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHALOOP_DATA_ROOT", "/tmp/alphaloop-data-test")
    assert resolve_data_root() == Path("/tmp/alphaloop-data-test")
