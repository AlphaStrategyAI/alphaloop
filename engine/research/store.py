from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from types import TracebackType
from typing import Any, Self, get_args, get_origin

import cattrs

from engine.metrics import SimulationReport
from engine.research.models import (
    Attempt,
    CoverageFloor,
    MethodDefinition,
    MethodRef,
    MethodSource,
    MethodUsage,
    Research,
    ReviewReport,
    Slot,
)
from engine.strategy import StrategySpec
from engine.verifiers import PitVerifierResult, VerificationReport, VerifierResult
from engine.research.round_store import RoundRecoveryMixin
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


def _is_named_change(cls: type) -> bool:
    return get_origin(cls) is tuple and get_args(cls) == (str, object)


def _structure_named_change(value: Any, _: type) -> tuple[str, object]:
    field_name, raw = value[0], value[1]
    if field_name == "coverage_floor" and isinstance(raw, dict):
        raw = CoverageFloor(**raw)
    return (str(field_name), raw)


CONVERTER = cattrs.Converter()
CONVERTER.register_unstructure_hook(datetime, lambda value: value.isoformat())
CONVERTER.register_structure_hook(datetime, lambda value, _: datetime.fromisoformat(value))
CONVERTER.register_unstructure_hook(date, lambda value: value.isoformat())
CONVERTER.register_structure_hook(
    date, lambda value, _: date.fromisoformat(value) if isinstance(value, str) else value
)
CONVERTER.register_unstructure_hook(Path, str)
CONVERTER.register_structure_hook(Path, lambda value, _: Path(value))
CONVERTER.register_structure_hook_func(_is_named_change, _structure_named_change)
CONVERTER.register_structure_hook_func(
    _is_slot_type,
    _structure_slot,
)


def _structure_verifier_result(item: dict[str, Any], _: type) -> VerifierResult:
    if item.get("verifier_id") != "pit.consistency":
        return CONVERTER.structure(item, VerifierResult)
    payload = dict(item)
    payload.setdefault("evidence_timestamps", [])
    payload.setdefault("backtest_cutoff", "")
    payload.setdefault("violations", [])
    payload.setdefault("evidence_used", 0)
    payload.setdefault("undated_excluded", [])
    payload.setdefault("scope", "")
    payload.setdefault("note", "")
    payload.setdefault("violation_details", [])
    return CONVERTER.structure(payload, PitVerifierResult)


def _structure_verification_report(data: Any, _: type) -> VerificationReport | None:
    if data is None:
        return None
    if isinstance(data, VerificationReport):
        return data
    if not isinstance(data, dict):
        raise TypeError("verification must decode to VerificationReport")
    return VerificationReport(
        tuple(_structure_verifier_result(item, VerifierResult) for item in data["results"])
    )


def _coerce_path(value: Any) -> Path | None:
    if value is None:
        return None
    return value if isinstance(value, Path) else Path(str(value))


def _coerce_path_tuple(value: Any) -> tuple[Path, ...]:
    if not value:
        return ()
    if isinstance(value, tuple):
        items = value
    elif isinstance(value, list):
        items = value
    else:
        return ()
    return tuple(item if isinstance(item, Path) else Path(str(item)) for item in items)


def _structure_attempt(data: dict[str, Any], _: type) -> Attempt:
    payload = dict(data)
    payload["verification"] = _structure_verification_report(payload.get("verification"), VerificationReport)
    if isinstance(payload.get("simulation"), dict):
        payload["simulation"] = CONVERTER.structure(payload["simulation"], SimulationReport)
    if isinstance(payload.get("spec"), dict):
        payload["spec"] = CONVERTER.structure(payload["spec"], StrategySpec)
    if isinstance(payload.get("review"), dict):
        payload["review"] = CONVERTER.structure(payload["review"], ReviewReport)
    payload["data_snapshot_path"] = _coerce_path(payload.get("data_snapshot_path"))
    payload["evidence_paths"] = _coerce_path_tuple(payload.get("evidence_paths"))
    return Attempt(**payload)


CONVERTER.register_structure_hook(VerificationReport, _structure_verification_report)
CONVERTER.register_structure_hook(Attempt, _structure_attempt)

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=30000;
CREATE TABLE IF NOT EXISTS researches (
    research_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_completed_round INTEGER NOT NULL DEFAULT 0,
    revision INTEGER NOT NULL DEFAULT 0,
    last_seq INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT '',
    create_command_id TEXT
);
CREATE TABLE IF NOT EXISTS research_event (
    research_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    version INTEGER,
    kind TEXT NOT NULL,
    refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (research_id, seq)
);
CREATE TABLE IF NOT EXISTS command_receipt (
    research_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    revision INTEGER NOT NULL,
    result_ref TEXT NOT NULL,
    status TEXT NOT NULL,
    bound_revision INTEGER,
    bound_version INTEGER,
    bound_snapshot TEXT,
    budget_reserved INTEGER NOT NULL DEFAULT 0,
    operation_key TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (research_id, command_id)
);
CREATE INDEX IF NOT EXISTS idx_research_event_research_seq
    ON research_event(research_id, seq);
CREATE UNIQUE INDEX IF NOT EXISTS idx_command_receipt_operation
    ON command_receipt(operation_key) WHERE operation_key IS NOT NULL;
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
CREATE TABLE IF NOT EXISTS data_window_round_counts (
    window_key TEXT PRIMARY KEY,
    cumulative_rounds INTEGER NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class Heartbeat:
    owner: str
    pid: int
    heartbeat_at: datetime


class ConcurrentWrite(RuntimeError):
    """The stored research changed after it was loaded."""


_WRITE_LOCKS: dict[str, threading.RLock] = {}
_WRITE_LOCKS_GUARD = threading.Lock()
_IMMEDIATE_RETRY_SEC = 5.0


def _database_write_lock(path: Path) -> threading.RLock:
    """One lock per database file, shared by every store opened on that path."""
    key = str(path.resolve())
    with _WRITE_LOCKS_GUARD:
        lock = _WRITE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _WRITE_LOCKS[key] = lock
        return lock


def _is_sqlite_busy(error: BaseException) -> bool:
    text = str(error).lower()
    return "locked" in text or "busy" in text


class _BufferedCursor:
    """Rows copied while the connection lock is held, so callers can read them after release."""

    def __init__(self, cursor: sqlite3.Cursor) -> None:
        self._rows = list(cursor.fetchall())
        self._index = 0
        self.rowcount = cursor.rowcount
        self.lastrowid = cursor.lastrowid

    def fetchone(self) -> Any:
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self) -> list[Any]:
        rows = self._rows[self._index :]
        self._index = len(self._rows)
        return rows


class _SerializedConnection:
    """Serialize use of one sqlite3 connection across ThreadingHTTPServer workers.

    A bare ``execute`` copies its rows before releasing the lock. ``with connection``
    holds the lock only for that transaction, so a market-data probe must stay outside it.

    A route poll's SELECT must not leave a read transaction open. On Python builds
    that keep that transaction alive, the next dialogue write raises
    ``database is locked`` even though both calls share this connection.

    ``serve`` also opens a second store on the same file for the research loop.
    A deferred journal transaction reads first, then upgrades to a write. If the
    loop store holds the write lock, SQLite returns ``database is locked``
    immediately and does not wait for ``busy_timeout``. Writers on one path share
    a lock, and the transaction starts with ``BEGIN IMMEDIATE`` so the reserved
    lock is taken before those reads.
    """

    def __init__(self, raw: sqlite3.Connection, path: Path) -> None:
        self._raw = raw
        self._lock = threading.RLock()
        self._writer = _database_write_lock(path)
        self._frames = 0

    def __enter__(self) -> Self:
        self._lock.acquire()
        self._frames += 1
        writer_acquired = False
        try:
            if self._frames == 1:
                self._writer.acquire()
                writer_acquired = True
                if self._raw.in_transaction:
                    self._raw.rollback()
                self._raw.__enter__()
                if self._raw.in_transaction:
                    self._raw.rollback()
                self._begin_immediate()
            else:
                self._raw.__enter__()
        except BaseException:
            self._frames -= 1
            if writer_acquired:
                self._writer.release()
            self._lock.release()
            raise
        return self

    def _begin_immediate(self) -> None:
        """Reserve the write lock. Retry only when SQLite returns without waiting."""
        deadline = time.monotonic() + _IMMEDIATE_RETRY_SEC
        delay = 0.01
        while True:
            started = time.monotonic()
            try:
                self._raw.execute("BEGIN IMMEDIATE")
                return
            except sqlite3.OperationalError as exc:
                if not _is_sqlite_busy(exc):
                    raise
                if self._raw.in_transaction:
                    self._raw.rollback()
                waited = time.monotonic() - started
                if waited >= 0.2 or time.monotonic() >= deadline:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 0.2)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        try:
            return self._raw.__exit__(exc_type, exc, tb)
        finally:
            self._frames -= 1
            if self._frames == 0:
                self._writer.release()
            self._lock.release()

    def execute(self, sql: str, parameters: Any = ()) -> Any:
        if self._frames:
            return self._raw.execute(sql, parameters)
        with self._lock:
            try:
                return _BufferedCursor(self._raw.execute(sql, parameters))
            finally:
                self._release_idle_read(sql)

    @staticmethod
    def _is_idle_read(sql: str) -> bool:
        head = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
        return head in {"SELECT", "PRAGMA", "EXPLAIN"}

    def _release_idle_read(self, sql: str) -> None:
        if self._frames or not self._is_idle_read(sql):
            return
        if self._raw.in_transaction:
            self._raw.rollback()

    def executemany(self, sql: str, seq_of_parameters: Any) -> Any:
        if self._frames:
            return self._raw.executemany(sql, seq_of_parameters)
        with self._lock:
            return self._raw.executemany(sql, seq_of_parameters)

    def executescript(self, sql_script: str) -> Any:
        if self._frames:
            return self._raw.executescript(sql_script)
        with self._lock:
            return self._raw.executescript(sql_script)

    def commit(self) -> None:
        with self._lock:
            self._raw.commit()

    def rollback(self) -> None:
        with self._lock:
            self._raw.rollback()


class SQLiteStore(RoundRecoveryMixin):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = _SerializedConnection(
            sqlite3.connect(path, check_same_thread=False, timeout=30.0),
            path,
        )
        self.connection.executescript(SCHEMA)
        self._migrate_method_schema()
        self._migrate_review_attempts_schema()
        self._migrate_command_journal()
        self._migrate_round_recovery()
        self._recover_pending_receipts()

    def _migrate_review_attempts_schema(self) -> None:
        row = self.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='review_attempts'"
        ).fetchone()
        if row is None:
            return
        ddl = row[0] or ""
        if "PRIMARY KEY (research_id, attempt_id)" in ddl:
            return
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE review_attempts_v2 (
                    attempt_id TEXT NOT NULL,
                    research_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    round_number INTEGER NOT NULL,
                    passed INTEGER NOT NULL,
                    attempt_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (research_id, attempt_id)
                );
                INSERT INTO review_attempts_v2 (
                    attempt_id, research_id, version_number, round_number,
                    passed, attempt_json, created_at
                )
                SELECT attempt_id, research_id, version_number, round_number,
                       passed, attempt_json, created_at
                  FROM review_attempts;
                DROP TABLE review_attempts;
                ALTER TABLE review_attempts_v2 RENAME TO review_attempts;
                """
            )

    def _migrate_command_journal(self) -> None:
        """Add revision, events, and receipts without rewriting research JSON."""
        self._ensure_column("researches", "revision", "revision INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("researches", "last_seq", "last_seq INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("researches", "status", "status TEXT NOT NULL DEFAULT ''")
        self._ensure_column("researches", "create_command_id", "create_command_id TEXT")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS research_event (
                research_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                version INTEGER,
                kind TEXT NOT NULL,
                refs_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (research_id, seq)
            );
            CREATE TABLE IF NOT EXISTS command_receipt (
                research_id TEXT NOT NULL,
                command_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                revision INTEGER NOT NULL,
                result_ref TEXT NOT NULL,
                status TEXT NOT NULL,
                bound_revision INTEGER,
                bound_version INTEGER,
                bound_snapshot TEXT,
                budget_reserved INTEGER NOT NULL DEFAULT 0,
                operation_key TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (research_id, command_id)
            );
            CREATE INDEX IF NOT EXISTS idx_researches_status ON researches(status);
            CREATE INDEX IF NOT EXISTS idx_researches_revision
                ON researches(research_id, revision, last_seq);
            CREATE INDEX IF NOT EXISTS idx_researches_create_command
                ON researches(create_command_id) WHERE create_command_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_research_event_research_seq
                ON research_event(research_id, seq);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_command_receipt_operation
                ON command_receipt(operation_key) WHERE operation_key IS NOT NULL;
            CREATE TABLE IF NOT EXISTS publish_authorization (
                research_id TEXT NOT NULL,
                command_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                snapshot_hash TEXT NOT NULL,
                private_path TEXT NOT NULL,
                final_path TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (research_id, command_id)
            );
            """
        )
        self._backfill_status_column()

    def _ensure_column(self, table: str, name: str, declaration: str) -> None:
        columns = {
            row[1]
            for row in self.connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if name in columns:
            return
        self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {declaration}")

    def _backfill_status_column(self) -> None:
        rows = self.connection.execute(
            "SELECT research_id, state_json, status FROM researches"
        ).fetchall()
        pending = []
        for research_id, state_json, status in rows:
            if status:
                continue
            try:
                parsed = json.loads(state_json)
            except json.JSONDecodeError:
                continue
            value = parsed.get("status") if isinstance(parsed, dict) else None
            if isinstance(value, str) and value:
                pending.append((value, research_id))
        if not pending:
            return
        with self.connection:
            self.connection.executemany(
                "UPDATE researches SET status=? WHERE research_id=? AND status=''",
                pending,
            )

    def _recover_pending_receipts(self) -> None:
        """A pending remote claim did not finish. Startup cannot prove the provider ran."""
        with self.connection:
            self.connection.execute(
                "UPDATE command_receipt SET status='unknown' WHERE status='pending'"
            )

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
        data = json.loads(payload)
        if isinstance(data, dict):
            data.setdefault("pending_non_mr_thesis", None)
            data.setdefault("mean_reversion_adopted", False)
            data.setdefault("mean_reversion_declined", False)
            data.setdefault("repicked_family", "")
            data.setdefault("symbol_probe_symbols", [])
            data.setdefault("symbol_probe_missing", [])
            data.setdefault("symbol_probe_unavailable", False)
            data.setdefault("dismissed_symbol_tokens", [])
            data.setdefault("market_switch_market", "")
            data.setdefault("market_switch_benchmark", "")
            data.setdefault("evidence_policy", None)
            data.setdefault("candidate_policy", None)
            data.setdefault("candidate_stop_reason", "")
            data.setdefault("candidate_stop_explanation", "")
            data.setdefault("reverification_audit", [])
            data.setdefault("logic_proposal", None)
            for key in ("pending_confirm", "logic_proposal"):
                pending = data.get(key)
                if isinstance(pending, dict):
                    pending.setdefault("return_status", None)
            for bucket in (data.get("reverifications"), data.get("reverification_audit")):
                for item in bucket or []:
                    if isinstance(item, dict):
                        item.setdefault("version_number", None)
                        item.setdefault("revision", "")
                        item.setdefault("input_hash", "")
            for item in data.get("exports") or []:
                if isinstance(item, dict):
                    item.setdefault("round_id", None)
                    item.setdefault("input_hash", None)
                    item.setdefault("method_revision", None)
                    item.setdefault("association", "")
                    item.setdefault("fingerprint", "")
                    item.setdefault("command_id", "")
            for version in data.get("versions") or []:
                if isinstance(version, dict):
                    version.setdefault("effective_spec_snapshot", None)
                    version.setdefault("parent_digest", None)
            universe = (
                data.get("brief", {}).get("universe", {}).get("value")
                if isinstance(data.get("brief"), dict)
                else None
            )
            if isinstance(universe, dict):
                universe.setdefault("unresolved_tokens", [])
                universe.setdefault("inferred_symbols", [])
                universe.setdefault("symbol_asks", [])
                universe.setdefault("symbol_ask_answers", [])
                universe.setdefault("ticker_hints", [])
                universe.setdefault("market_mismatches", [])
                universe.setdefault("unrecognized_tokens", [])
                universe.setdefault("market_unspecified", False)
                asks = universe.get("symbol_asks") or []
                normalized = []
                for item in asks:
                    if isinstance(item, list) and len(item) == 2:
                        normalized.append([item[0], item[1], "ask"])
                    else:
                        normalized.append(item)
                universe["symbol_asks"] = normalized
                universe.setdefault("recognition_hidden", False)
        return CONVERTER.structure(data, Research)

    def create(self, research: Research) -> None:
        from engine.research.removal import forget_research_removed

        forget_research_removed(research.research_id)
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO researches(
                    research_id,state_json,updated_at,status,revision,last_seq
                ) VALUES(?,?,?,?,0,0)
                """,
                (
                    research.research_id,
                    self._encode(research),
                    research.updated_at.isoformat(),
                    research.status.value,
                ),
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
                   SET state_json=?, updated_at=?, last_completed_round=?, status=?
                 WHERE research_id=? AND updated_at=?
                """,
                (
                    self._encode(research),
                    research.updated_at.isoformat(),
                    completed,
                    research.status.value,
                    research.research_id,
                    expected_updated_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                raise ConcurrentWrite(research.research_id)

    def save_with_event(
        self,
        research: Research,
        expected_updated_at: datetime,
        kind: str,
        refs: dict[str, Any] | None = None,
    ) -> int:
        """Legacy domain write: CAS, bump revision, append one event. No command receipt."""
        with self.connection:
            row = self.connection.execute(
                """
                SELECT revision FROM researches
                 WHERE research_id=? AND updated_at=?
                """,
                (research.research_id, expected_updated_at.isoformat()),
            ).fetchone()
            if row is None:
                raise ConcurrentWrite(research.research_id)
            return self.cas_research_and_event(
                research,
                expected_updated_at=expected_updated_at.isoformat(),
                expected_revision=int(row[0]),
                kind=kind,
                refs=refs or {},
            )

    def cas_research_and_event(
        self,
        research: Research,
        *,
        expected_updated_at: str,
        expected_revision: int,
        kind: str,
        refs: dict[str, Any],
    ) -> int:
        """Caller holds the connection transaction. Returns the new revision."""
        row = self.connection.execute(
            """
            SELECT revision, last_seq FROM researches
             WHERE research_id=? AND updated_at=? AND revision=?
            """,
            (research.research_id, expected_updated_at, expected_revision),
        ).fetchone()
        if row is None:
            raise ConcurrentWrite(research.research_id)
        revision = int(row[0]) + 1
        seq = int(row[1]) + 1
        completed = sum(len(version.rounds) for version in research.versions)
        cursor = self.connection.execute(
            """
            UPDATE researches
               SET state_json=?, updated_at=?, last_completed_round=?, status=?,
                   revision=?, last_seq=?
             WHERE research_id=? AND updated_at=? AND revision=?
            """,
            (
                self._encode(research),
                research.updated_at.isoformat(),
                completed,
                research.status.value,
                revision,
                seq,
                research.research_id,
                expected_updated_at,
                expected_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise ConcurrentWrite(research.research_id)
        version = research.current_version_number
        self.connection.execute(
            """
            INSERT INTO research_event(
                research_id, seq, version, kind, refs_json, created_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (
                research.research_id,
                seq,
                version,
                kind,
                json.dumps(refs, sort_keys=True, separators=(",", ":")),
                research.updated_at.isoformat(),
            ),
        )
        return revision

    def revision_of(self, research_id: str) -> int:
        row = self.connection.execute(
            "SELECT revision FROM researches WHERE research_id=?",
            (research_id,),
        ).fetchone()
        if row is None:
            raise KeyError(research_id)
        return int(row[0])

    def revision_map(self) -> dict[str, int]:
        rows = self.connection.execute(
            "SELECT research_id, revision FROM researches"
        ).fetchall()
        return {str(research_id): int(revision) for research_id, revision in rows}

    def research_head(self, research_id: str) -> tuple[int, int, str, str, str | None] | None:
        """revision, last_seq, updated_at, state_json, create_command_id."""
        row = self.connection.execute(
            """
            SELECT revision, last_seq, updated_at, state_json, create_command_id
              FROM researches WHERE research_id=?
            """,
            (research_id,),
        ).fetchone()
        if row is None:
            return None
        return int(row[0]), int(row[1]), str(row[2]), str(row[3]), row[4]

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
                ON CONFLICT(research_id, attempt_id) DO NOTHING
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

    def get_attempt(
        self,
        record_id: str,
        *,
        research_id: str | None = None,
    ) -> dict[str, Any] | None:
        if research_id is not None:
            row = self.connection.execute(
                """
                SELECT attempt_json FROM review_attempts
                 WHERE research_id=? AND attempt_id=?
                """,
                (research_id, record_id),
            ).fetchone()
            if row is not None:
                return json.loads(row[0])
        else:
            rows = self.connection.execute(
                "SELECT attempt_json FROM review_attempts WHERE attempt_id=?",
                (record_id,),
            ).fetchall()
            if len(rows) == 1:
                return json.loads(rows[0][0])
            if len(rows) > 1:
                return None
        for research in self.list_research():
            if research_id is not None and research.research_id != research_id:
                continue
            for version in research.versions:
                for round_ in version.rounds:
                    if round_.accepted_attempt.attempt_id == record_id:
                        return {"attempt_id": record_id}
        return None

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

    def clear_review_attempts(
        self,
        research_id: str,
        version_number: int,
        round_number: int,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                DELETE FROM review_attempts
                 WHERE research_id=? AND version_number=? AND round_number=?
                """,
                (research_id, version_number, round_number),
            )

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
        rows = self.connection.execute("SELECT status FROM researches").fetchall()
        states = [str(row[0]) for row in rows]
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

    def _all_method_revision_rows(self) -> tuple[MethodDefinition, ...]:
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

    def list_method_definitions(self) -> tuple[MethodDefinition, ...]:
        latest: dict[str, MethodDefinition] = {}
        for item in self._all_method_revision_rows():
            current = latest.get(item.method_id)
            if current is None or item.created_at >= current.created_at:
                latest[item.method_id] = item
        return tuple(latest[method_id] for method_id in sorted(latest))

    def get_method_definition(
        self, method_id: str, revision_hash: str
    ) -> MethodDefinition | None:
        for item in self._all_method_revision_rows():
            if item.method_id == method_id and item.revision_hash == revision_hash:
                return item
        return None

    def latest_method_definition(self, method_id: str) -> MethodDefinition | None:
        rows = [item for item in self._all_method_revision_rows() if item.method_id == method_id]
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
            """
            SELECT research_id FROM researches
             WHERE status=?
             ORDER BY research_id
            """,
            ("running",),
        ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def delete(self, research_id: str) -> None:
        from engine.research.removal import mark_research_removed

        mark_research_removed(research_id)
        with self.connection:
            self.connection.execute(
                "DELETE FROM review_attempts WHERE research_id=?",
                (research_id,),
            )
            self.connection.execute(
                "DELETE FROM method_usage WHERE research_id=?",
                (research_id,),
            )
            self.connection.execute(
                "DELETE FROM engine_errors WHERE research_id=?",
                (research_id,),
            )
            self.connection.execute(
                "DELETE FROM research_event WHERE research_id=?",
                (research_id,),
            )
            self.connection.execute(
                "DELETE FROM command_receipt WHERE research_id=?",
                (research_id,),
            )
            self.connection.execute(
                "DELETE FROM researches WHERE research_id=?",
                (research_id,),
            )
            self.connection.execute(
                "DELETE FROM step_run WHERE research_id=?",
                (research_id,),
            )
            self.connection.execute(
                "DELETE FROM committed_round WHERE research_id=?",
                (research_id,),
            )
            self.connection.execute(
                "DELETE FROM committed_candidate WHERE research_id=?",
                (research_id,),
            )
            self.connection.execute(
                "DELETE FROM window_round_ledger WHERE research_id=?",
                (research_id,),
            )
            self.connection.execute(
                "DELETE FROM round_receipt WHERE research_id=?",
                (research_id,),
            )
            self.connection.execute(
                "DELETE FROM compute_lease WHERE research_id=?",
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

    def window_round_count(self, window_key: str) -> int:
        row = self.connection.execute(
            "SELECT cumulative_rounds FROM data_window_round_counts WHERE window_key=?",
            (window_key,),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def increment_window_round_count(self, window_key: str) -> int:
        with self.connection:
            row = self.connection.execute(
                "SELECT cumulative_rounds FROM data_window_round_counts WHERE window_key=?",
                (window_key,),
            ).fetchone()
            next_count = (int(row[0]) if row is not None else 0) + 1
            self.connection.execute(
                """
                INSERT INTO data_window_round_counts(window_key, cumulative_rounds)
                VALUES(?, ?)
                ON CONFLICT(window_key) DO UPDATE SET cumulative_rounds=excluded.cumulative_rounds
                """,
                (window_key, next_count),
            )
        return next_count

    def record_error(
        self,
        research_id: str,
        message: str,
        now: datetime,
        *,
        force: bool = False,
    ) -> None:
        if not force:
            recent = self.connection.execute(
                """
                SELECT created_at FROM engine_errors
                 WHERE research_id=? AND message=?
                 ORDER BY created_at DESC LIMIT 1
                """,
                (research_id, message),
            ).fetchone()
            if recent is not None:
                last = datetime.fromisoformat(recent[0])
                if (now - last).total_seconds() < 300:
                    return
        with self.connection:
            self.connection.execute(
                "INSERT INTO engine_errors(research_id,message,created_at) VALUES(?,?,?)",
                (research_id, message, now.isoformat()),
            )

    def get_publish_authorization(self, research_id: str, command_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT kind, fingerprint, snapshot_hash, private_path, final_path,
                   receipt_json, created_at
              FROM publish_authorization
             WHERE research_id=? AND command_id=?
            """,
            (research_id, command_id),
        ).fetchone()
        if row is None:
            return None
        return {
            "research_id": research_id,
            "command_id": command_id,
            "kind": row[0],
            "fingerprint": row[1],
            "snapshot_hash": row[2],
            "private_path": row[3],
            "final_path": row[4],
            "receipt_json": row[5],
            "created_at": row[6],
        }

    def insert_publish_authorization(
        self,
        *,
        research_id: str,
        command_id: str,
        kind: str,
        fingerprint: str,
        snapshot_hash: str,
        private_path: str,
        final_path: str,
        receipt_json: str,
        created_at: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO publish_authorization(
                    research_id, command_id, kind, fingerprint, snapshot_hash,
                    private_path, final_path, receipt_json, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    research_id,
                    command_id,
                    kind,
                    fingerprint,
                    snapshot_hash,
                    private_path,
                    final_path,
                    receipt_json,
                    created_at,
                ),
            )
