"""review_attempts composite primary key and migration."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.research.models import ChangeClass, Attempt, ReviewReport
from engine.research.store import SQLiteStore
from tests.test_loop_runtime import NOW, strategy

RESEARCH_A = "research-a"
RESEARCH_B = "research-b"


def _attempt(attempt_id: str) -> Attempt:
    return Attempt(
        attempt_id=attempt_id,
        number=1,
        change_class=ChangeClass.PARAM,
        spec=strategy(1),
        simulation=None,
        verification=None,
        review=ReviewReport(True, ()),
    )


def test_two_researches_same_attempt_id_in_one_database(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "shared.db")
    shared_id = "v1-r1-a1"
    store.record_review_attempt(RESEARCH_A, 1, 1, _attempt(shared_id), NOW)
    store.record_review_attempt(RESEARCH_B, 1, 1, _attempt(shared_id), NOW)

    assert store.get_attempt(shared_id, research_id=RESEARCH_A) is not None
    assert store.get_attempt(shared_id, research_id=RESEARCH_B) is not None
    assert store.get_attempt(shared_id) is None


def test_migrates_legacy_global_attempt_id_primary_key(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE review_attempts (
            attempt_id TEXT PRIMARY KEY,
            research_id TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            passed INTEGER NOT NULL,
            attempt_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        INSERT INTO review_attempts VALUES (
            'v1-r1-a1', 'old-research', 1, 1, 1, '{"attempt_id":"v1-r1-a1"}', '2026-01-01T00:00:00+00:00'
        );
        """
    )
    connection.close()

    store = SQLiteStore(path)
    row = store.connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='review_attempts'"
    ).fetchone()
    assert row is not None
    assert "PRIMARY KEY (research_id, attempt_id)" in row[0]

    store.record_review_attempt(RESEARCH_B, 1, 1, _attempt("v1-r1-a1"), NOW)
    assert store.get_attempt("v1-r1-a1", research_id="old-research") is not None
    assert store.get_attempt("v1-r1-a1", research_id=RESEARCH_B) is not None

    store2 = SQLiteStore(path)
    assert store2.get_attempt("v1-r1-a1", research_id=RESEARCH_B) is not None


def test_migration_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "once.db"
    SQLiteStore(path)
    SQLiteStore(path)
    row = sqlite3.connect(path).execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='review_attempts'"
    ).fetchone()
    assert "PRIMARY KEY (research_id, attempt_id)" in row[0]
