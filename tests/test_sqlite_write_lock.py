"""Packaged macOS e2e hit ``database is locked`` on a journal commit.

The engine opens two stores on one file. A dialogue commit reads inside a
deferred transaction, then updates. The loop store can take the write lock
in between. SQLite then refuses the upgrade immediately and ignores
``busy_timeout``. The open write must already hold the reserved lock.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.research.store import SQLiteStore

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def _insert(store: SQLiteStore, research_id: str) -> None:
    store.connection._raw.execute(
        """
        INSERT INTO researches(research_id, state_json, updated_at, status)
        VALUES(?,?,?,?)
        """,
        (research_id, "{}", NOW.isoformat(), "draft"),
    )
    store.connection._raw.commit()


def test_open_write_reserves_the_lock_before_the_read(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "lock.db")
    _insert(store, "r-lock")
    other = sqlite3.connect(store.path, timeout=0.2, check_same_thread=False)
    other.execute("PRAGMA busy_timeout=200")
    try:
        with store.connection:
            store.connection.execute(
                "SELECT research_id FROM researches WHERE research_id=?",
                ("r-lock",),
            ).fetchall()
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                other.execute("BEGIN IMMEDIATE")
            store.connection.execute(
                "UPDATE researches SET status=status WHERE research_id=?",
                ("r-lock",),
            )
    finally:
        other.close()


def test_second_store_writer_does_not_fail_the_overlapping_update(tmp_path: Path) -> None:
    """Same shape as ``serve``: loop store and command store, one database."""
    path = tmp_path / "two.db"
    loop = SQLiteStore(path)
    api = SQLiteStore(path)
    _insert(api, "r-two")
    started = threading.Event()

    def hold_loop_write() -> None:
        with loop.connection:
            loop.connection.execute(
                "UPDATE researches SET status=status WHERE research_id=?",
                ("r-two",),
            )
            started.set()
            threading.Event().wait(0.3)

    thread = threading.Thread(target=hold_loop_write)
    thread.start()
    assert started.wait(2.0)
    try:
        with api.connection:
            api.connection.execute(
                "SELECT revision FROM researches WHERE research_id=?",
                ("r-two",),
            ).fetchall()
            api.connection.execute(
                "UPDATE researches SET revision=revision WHERE research_id=?",
                ("r-two",),
            )
    finally:
        thread.join(5.0)
    assert not thread.is_alive()
    row = api.connection.execute(
        "SELECT revision FROM researches WHERE research_id=?",
        ("r-two",),
    ).fetchone()
    assert row is not None
