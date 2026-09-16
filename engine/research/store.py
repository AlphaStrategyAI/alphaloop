from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, get_args, get_origin

import cattrs

from engine.research.models import (
    Attempt,
    CoverageFloor,
    MethodDefinition,
    MethodRef,
    MethodSource,
    MethodUsage,
    Research,
    Slot,
)
from engine.research.runtime import OwnerRecord


def _deep_unstructure(value: Any) -> Any:
    """Recursively convert any value to JSON-serializable form."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_deep_unstructure(item) for item in value]
    if isinstance(value, list):
        return [_deep_unstructure(item) for item in value]
    if isinstance(value, dict):
        return {k: _deep_unstructure(v) for k, v in value.items()}
    if is_dataclass(value) and not isinstance(value, type):
        result = {}
        for f in fields(value):
            result[f.name] = _deep_unstructure(getattr(value, f.name))
        return result
    return value


def _structure_slot(data: dict[str, Any], typ: type) -> Slot[Any]:
    inner_type = get_args(typ)[0] if get_args(typ) else Any
    raw_value = data["value"]
    if raw_value is None:
        structured_value = None
    elif isinstance(raw_value, dict) and set(raw_value.keys()) == {"min_assets", "min_years", "max_missing_pct"}:
        structured_value = CoverageFloor(**raw_value)
    else:
        structured_value = CONVERTER.structure(raw_value, inner_type)
    return Slot(structured_value, data["locked"])


def _is_slot_type(cls: type) -> bool:
    """Check if cls is Slot or a generic instantiation of Slot."""
    return cls is Slot or get_origin(cls) is Slot


CONVERTER = cattrs.Converter()
CONVERTER.register_unstructure_hook(datetime, lambda value: value.isoformat())
CONVERTER.register_structure_hook(datetime, lambda value, _: datetime.fromisoformat(value))
CONVERTER.register_unstructure_hook(date, lambda value: value.isoformat())
CONVERTER.register_structure_hook(
    date, lambda value, _: date.fromisoformat(value) if isinstance(value, str) else value
)
CONVERTER.register_unstructure_hook(Path, str)
CONVERTER.register_structure_hook(Path, lambda value, _: Path(value))
CONVERTER.register_structure_hook_func(
    _is_slot_type,
    _structure_slot,
)

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS researches (
    research_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_completed_round INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS engine_heartbeat (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    owner TEXT NOT NULL,
    pid INTEGER NOT NULL,
    heartbeat_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_attempts (
    attempt_id TEXT PRIMARY KEY,
    research_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    attempt_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS method_revisions (
    method_id TEXT NOT NULL,
    revision_hash TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL,
    body TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'preset',
    deposited_from_research_id TEXT,
    supersedes TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (method_id, revision_hash)
);
CREATE TABLE IF NOT EXISTS method_usage (
    method_id TEXT NOT NULL,
    revision_hash TEXT NOT NULL,
    research_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    PRIMARY KEY (method_id, revision_hash, research_id, version_number)
);
CREATE TABLE IF NOT EXISTS engine_errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_id TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class Heartbeat:
    owner: str
    pid: int
    heartbeat_at: datetime


class ConcurrentWrite(RuntimeError):
    """The stored research changed after it was loaded."""


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.executescript(SCHEMA)
        self._migrate_method_schema()

    def _migrate_method_schema(self) -> None:
        columns = {
            row[1]
            for row in self.connection.execute("PRAGMA table_info(method_revisions)").fetchall()
        }
        if "body" in columns:
            return
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE method_revisions_v2 (
                    method_id TEXT NOT NULL,
                    revision_hash TEXT NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL,
                    body TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'preset',
                    deposited_from_research_id TEXT,
                    supersedes TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (method_id, revision_hash)
                );
                INSERT INTO method_revisions_v2 (
                    method_id, revision_hash, name, description, body, source, created_at
                )
                SELECT method_id, revision_hash, '', definition, definition, 'preset', created_at
                  FROM method_revisions;
                DROP TABLE method_revisions;
                ALTER TABLE method_revisions_v2 RENAME TO method_revisions;
                """
            )

    @staticmethod
    def _encode(research: Research) -> str:
        return json.dumps(_deep_unstructure(research), sort_keys=True)

    @staticmethod
    def _decode(payload: str) -> Research:
        return CONVERTER.structure(json.loads(payload), Research)

    def create(self, research: Research) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO researches(research_id,state_json,updated_at) VALUES(?,?,?)",
                (research.research_id, self._encode(research), research.updated_at.isoformat()),
            )

    def load(self, research_id: str) -> Research:
        row = self.connection.execute(
            "SELECT state_json FROM researches WHERE research_id=?",
            (research_id,),
        ).fetchone()
        if row is None:
            raise KeyError(research_id)
        return self._decode(row[0])

    def save(self, research: Research, expected_updated_at: datetime) -> None:
        completed = sum(len(version.rounds) for version in research.versions)
        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE researches
                   SET state_json=?, updated_at=?, last_completed_round=?
                 WHERE research_id=? AND updated_at=?
                """,
                (
                    self._encode(research),
                    research.updated_at.isoformat(),
                    completed,
                    research.research_id,
                    expected_updated_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                raise ConcurrentWrite(research.research_id)

    def last_completed_round(self, research_id: str) -> int:
        row = self.connection.execute(
            "SELECT last_completed_round FROM researches WHERE research_id=?",
            (research_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    def record_review_attempt(
        self,
        research_id: str,
        version_number: int,
        round_number: int,
        attempt: Attempt,
        now: datetime,
    ) -> None:
        if attempt.review is None:
            raise ValueError("review attempt must contain ReviewReport")
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO review_attempts(
                    attempt_id,research_id,version_number,round_number,
                    passed,attempt_json,created_at
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    attempt.attempt_id,
                    research_id,
                    version_number,
                    round_number,
                    int(attempt.review.passed),
                    json.dumps(_deep_unstructure(attempt), sort_keys=True),
                    now.isoformat(),
                ),
            )

    def review_failure_count(
        self,
        research_id: str,
        version_number: int,
        round_number: int,
    ) -> int:
        row = self.connection.execute(
            """
            SELECT COUNT(*) FROM review_attempts
             WHERE research_id=? AND version_number=? AND round_number=? AND passed=0
            """,
            (research_id, version_number, round_number),
        ).fetchone()
        return int(row[0])

    def heartbeat(self, owner: OwnerRecord, now: datetime) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO engine_heartbeat(singleton,owner,pid,heartbeat_at)
                VALUES(1,?,?,?)
                ON CONFLICT(singleton) DO UPDATE SET
                    owner=excluded.owner,pid=excluded.pid,heartbeat_at=excluded.heartbeat_at
                """,
                (owner.owner, owner.pid, now.isoformat()),
            )

    def read_heartbeat(self) -> Heartbeat:
        row = self.connection.execute(
            "SELECT owner,pid,heartbeat_at FROM engine_heartbeat WHERE singleton=1"
        ).fetchone()
        if row is None:
            raise LookupError("heartbeat unavailable")
        return Heartbeat(row[0], int(row[1]), datetime.fromisoformat(row[2]))

    def status_flags(self) -> tuple[bool, bool]:
        rows = self.connection.execute("SELECT state_json FROM researches").fetchall()
        states = [json.loads(row[0])["status"] for row in rows]
        return "running" in states, "awaiting_confirm" in states

    def list_research(self) -> tuple[Research, ...]:
        rows = self.connection.execute(
            "SELECT state_json FROM researches ORDER BY updated_at DESC"
        ).fetchall()
        return tuple(self._decode(row[0]) for row in rows)

    def list_methods(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(
            (item.method_id, item.revision_hash, item.description)
            for item in self.list_method_definitions()
        )

    def list_method_definitions(self) -> tuple[MethodDefinition, ...]:
        rows = self.connection.execute(
            """
            SELECT method_id,revision_hash,name,description,body,source,
                   deposited_from_research_id,supersedes,created_at
              FROM method_revisions
             ORDER BY rowid
            """
        ).fetchall()
        return tuple(
            MethodDefinition(
                method_id=row[0],
                revision_hash=row[1],
                name=row[2],
                description=row[3],
                body=row[4],
                source=MethodSource(row[5]),
                deposited_from_research_id=row[6],
                created_at=datetime.fromisoformat(row[8]),
                supersedes=row[7],
            )
            for row in rows
        )

    def latest_method_definition(self, method_id: str) -> MethodDefinition | None:
        rows = [item for item in self.list_method_definitions() if item.method_id == method_id]
        if not rows:
            return None
        superseded = {item.supersedes for item in rows if item.supersedes}
        heads = [item for item in rows if item.revision_hash not in superseded]
        return heads[-1] if heads else rows[-1]

    def insert_method_definition(self, definition: MethodDefinition) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO method_revisions(
                    method_id,revision_hash,name,description,body,source,
                    deposited_from_research_id,supersedes,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    definition.method_id,
                    definition.revision_hash,
                    definition.name,
                    definition.description,
                    definition.body,
                    definition.source.value,
                    definition.deposited_from_research_id,
                    definition.supersedes,
                    definition.created_at.isoformat(),
                ),
            )

    def list_method_usage(self, method_id: str) -> tuple[MethodUsage, ...]:
        rows = self.connection.execute(
            """
            SELECT method_id,revision_hash,research_id,version_number
              FROM method_usage
             WHERE method_id=?
             ORDER BY rowid
            """,
            (method_id,),
        ).fetchall()
        return tuple(MethodUsage(row[0], row[1], row[2], int(row[3])) for row in rows)

    def record_method_usage(
        self,
        research_id: str,
        version_number: int,
        method_set: tuple[MethodRef, ...],
    ) -> None:
        with self.connection:
            self.connection.executemany(
                """
                INSERT OR IGNORE INTO method_usage(
                    method_id,revision_hash,research_id,version_number
                ) VALUES(?,?,?,?)
                """,
                [
                    (item.method_id, item.revision_hash, research_id, version_number)
                    for item in method_set
                ],
            )

    def running_ids(self) -> tuple[str, ...]:
        rows = self.connection.execute(
            "SELECT research_id,state_json FROM researches ORDER BY research_id"
        ).fetchall()
        return tuple(
            research_id
            for research_id, payload in rows
            if json.loads(payload)["status"] == "running"
        )

    def delete(self, research_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM researches WHERE research_id=?",
                (research_id,),
            )

    def revise_method(
        self,
        method_id: str,
        definition: str,
        now: datetime,
        name: str = "",
        body: str | None = None,
        source: str = "preset",
        supersedes: str | None = None,
        deposited_from_research_id: str | None = None,
    ) -> str:
        text = definition if body is None else body
        row = MethodDefinition(
            method_id=method_id,
            revision_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            name=name,
            description=definition,
            body=text,
            source=source if isinstance(source, MethodSource) else MethodSource(source),
            deposited_from_research_id=deposited_from_research_id,
            created_at=now,
            supersedes=supersedes,
        )
        self.insert_method_definition(row)
        return row.revision_hash

    def record_error(self, research_id: str, message: str, now: datetime) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO engine_errors(research_id,message,created_at) VALUES(?,?,?)",
                (research_id, message, now.isoformat()),
            )
