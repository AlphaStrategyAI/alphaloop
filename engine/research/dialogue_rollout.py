"""Gray enablement for dialogue-driven research, and the rollback gate.

The product default is off. Settings key ``dialogueDrivenResearchEnabled``
wins over ``ALPHALOOP_DIALOGUE_V2``. A closed write gate wins over both: new
dialogue writes stop, and the command journal stays in place.

This module is the release switch. It does not score the holdout set.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.research.candidates import POLICY_VERSION
from engine.research.models import Research, ResearchEvent, ResearchStatus
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError

DIALOGUE_V2_KEY = "dialogueDrivenResearchEnabled"
ENV_KEY = "ALPHALOOP_DIALOGUE_V2"
GATE_FILE_NAME = "dialogue-write-gate.json"
KNOWN_PLANNER_REVISIONS = frozenset({POLICY_VERSION, "legacy-plus-5"})
KNOWN_METHOD_ALIASES = frozenset(
    {
        "walk-v1",
        "stability-v1",
        "crowding-v1",
        "cost-v1",
        "scorecard-v1",
        "pit-v1",
        "pit-v2",
    }
)
KILL_REASONS = frozenset(
    {
        "unauthorized_execution",
        "duplicate_open_version",
        "unauthorized_resend",
        "duplicate_m",
        "frozen_data_drift",
        "lost_committed_receipt",
    }
)
_TRUE_ENV = frozenset({"1", "true", "yes", "on"})


def _now(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(UTC)


def _read_settings(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return loaded


def _write_settings(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    os.replace(temporary, path)


def dialogue_v2_enabled(settings_path: Path | None) -> bool:
    """Explicit settings boolean wins. Otherwise the env override, else off."""
    loaded = _read_settings(settings_path)
    if DIALOGUE_V2_KEY in loaded:
        return loaded[DIALOGUE_V2_KEY] is True
    raw = os.environ.get(ENV_KEY)
    if raw is None or not raw.strip():
        return False
    return raw.strip().lower() in _TRUE_ENV


def write_dialogue_enabled(settings_path: Path, enabled: bool) -> None:
    payload = _read_settings(settings_path)
    payload[DIALOGUE_V2_KEY] = bool(enabled)
    _write_settings(settings_path, payload)


def ensure_rollout_tables(store: SQLiteStore) -> None:
    store.connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS dialogue_write_gate (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            closed INTEGER NOT NULL,
            reason TEXT NOT NULL,
            detail TEXT NOT NULL,
            closed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS version_open_claim (
            research_id TEXT NOT NULL,
            command_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (research_id, command_id)
        );
        CREATE TABLE IF NOT EXISTS frozen_snapshot_seal (
            research_id TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            PRIMARY KEY (research_id, relative_path)
        );
        """
    )


def gate_file(store: SQLiteStore) -> Path:
    return store.path.parent / GATE_FILE_NAME


def write_gate(store: SQLiteStore) -> dict[str, Any] | None:
    ensure_rollout_tables(store)
    row = store.connection.execute(
        "SELECT closed, reason, detail, closed_at FROM dialogue_write_gate WHERE singleton=1"
    ).fetchone()
    if row is None or int(row[0]) != 1:
        return None
    return {
        "closed": True,
        "reason": str(row[1]),
        "detail": str(row[2]),
        "closed_at": str(row[3]),
    }


def publish_gate_file(store: SQLiteStore) -> None:
    path = gate_file(store)
    current = write_gate(store)
    if current is None:
        if path.is_file():
            path.unlink()
        return
    path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_gate_closed(store: SQLiteStore) -> bool:
    return write_gate(store) is not None


def new_dialogue_writes_open(store: SQLiteStore | None, settings_path: Path | None) -> bool:
    if store is not None and write_gate_closed(store):
        return False
    return dialogue_v2_enabled(settings_path)


def trip_write_gate(
    store: SQLiteStore,
    reason: str,
    detail: str,
    *,
    now: datetime | None = None,
) -> bool:
    """Close new dialogue writes. The first reason sticks. Journal rows stay."""
    if reason not in KILL_REASONS:
        raise ValueError(f"unknown write-gate reason: {reason}")
    ensure_rollout_tables(store)
    if write_gate_closed(store):
        return False
    stamp = _now(now).isoformat()
    with store.connection:
        store.connection.execute(
            """
            INSERT INTO dialogue_write_gate(singleton, closed, reason, detail, closed_at)
            VALUES (1, 1, ?, ?, ?)
            """,
            (reason, detail[:500], stamp),
        )
    publish_gate_file(store)
    return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def seal_snapshot(store: SQLiteStore, research_id: str, path: Path) -> str:
    """Record a linked snapshot hash relative to the database directory."""
    ensure_rollout_tables(store)
    root = store.path.parent.resolve()
    absolute = path.resolve()
    relative = absolute.relative_to(root).as_posix()
    digest = _sha256(absolute)
    with store.connection:
        store.connection.execute(
            """
            INSERT INTO frozen_snapshot_seal(research_id, relative_path, sha256)
            VALUES(?,?,?)
            ON CONFLICT(research_id, relative_path) DO UPDATE SET sha256=excluded.sha256
            """,
            (research_id, relative, digest),
        )
    return digest


def _snapshot_fault(store: SQLiteStore) -> str | None:
    ensure_rollout_tables(store)
    rows = store.connection.execute(
        "SELECT research_id, relative_path, sha256 FROM frozen_snapshot_seal"
    ).fetchall()
    root = store.path.parent
    for research_id, relative, digest in rows:
        path = root / str(relative)
        if not path.is_file() or _sha256(path) != str(digest):
            return f"{research_id}:{relative}"
    return None


def _duplicate_m_fault(store: SQLiteStore) -> str | None:
    rows = store.connection.execute(
        """
        SELECT c.window_key, c.cumulative_rounds,
               (SELECT COUNT(*) FROM window_round_ledger l WHERE l.window_key = c.window_key)
          FROM data_window_round_counts c
        """
    ).fetchall()
    for window_key, cumulative, ledger_count in rows:
        if int(ledger_count) > 0 and int(cumulative) > int(ledger_count):
            return f"{window_key}: M {cumulative} > ledger {ledger_count}"
    return None


def _lost_receipt_fault(store: SQLiteStore) -> str | None:
    row = store.connection.execute(
        """
        SELECT c.research_id, c.round_id
          FROM committed_round c
          LEFT JOIN round_receipt r
            ON c.research_id = r.research_id
           AND c.version_number = r.version_number
           AND c.round_number = r.round_number
         WHERE r.round_id IS NULL
         LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    return f"{row[0]}:{row[1]}"


def audit_and_trip(store: SQLiteStore, *, now: datetime | None = None) -> str | None:
    """Close the gate when a stored fault is already visible. First reason wins."""
    if write_gate_closed(store):
        return write_gate(store)["reason"] if write_gate(store) else None
    checks = (
        ("duplicate_m", _duplicate_m_fault),
        ("frozen_data_drift", _snapshot_fault),
        ("lost_committed_receipt", _lost_receipt_fault),
    )
    for reason, probe in checks:
        detail = probe(store)
        if detail:
            trip_write_gate(store, reason, detail, now=now)
            return reason
    return None


@contextmanager
def version_open_guard(
    store: SQLiteStore,
    research_id: str,
    command_id: str,
    now: datetime | None = None,
) -> Iterator[None]:
    """One command id may open one version. A second attempt closes new writes."""
    command_id = command_id.strip()
    if not command_id:
        yield
        return
    ensure_rollout_tables(store)
    stamp = _now(now).isoformat()
    try:
        with store.connection:
            store.connection.execute(
                """
                INSERT INTO version_open_claim(research_id, command_id, created_at)
                VALUES(?,?,?)
                """,
                (research_id, command_id, stamp),
            )
    except sqlite3.IntegrityError:
        trip_write_gate(
            store,
            "duplicate_open_version",
            f"{research_id}:{command_id}",
            now=now,
        )
        raise UserFacingError(
            "DUPLICATE_OPEN_VERSION",
            "这个命令已经开过一版。新增写入口已关闭，journal 仍保留。",
        ) from None
    try:
        yield
    except Exception:
        with store.connection:
            store.connection.execute(
                "DELETE FROM version_open_claim WHERE research_id=? AND command_id=?",
                (research_id, command_id),
            )
        raise


def note_unauthorized_execution(store: SQLiteStore, detail: str, *, now: datetime | None = None) -> None:
    trip_write_gate(store, "unauthorized_execution", detail, now=now)


def note_unauthorized_resend(store: SQLiteStore, detail: str, *, now: datetime | None = None) -> None:
    trip_write_gate(store, "unauthorized_resend", detail, now=now)


def _method_revision(ref: object) -> tuple[str, str]:
    method_id = str(getattr(ref, "method_id", "") or "")
    revision = getattr(ref, "revision_hash", None)
    if revision is None:
        revision = getattr(ref, "revision", "")
    return method_id, str(revision or "")


def _method_known(store: SQLiteStore, method_id: str, revision: str) -> bool:
    if not method_id or not revision or revision in KNOWN_METHOD_ALIASES:
        return True
    row = store.connection.execute(
        "SELECT 1 FROM method_revisions WHERE method_id=? AND revision_hash=?",
        (method_id, revision),
    ).fetchone()
    return row is not None


def revision_pause_reason(store: SQLiteStore, research: Research) -> str | None:
    """Running work keeps its frozen planner and method revisions.

    An unknown revision pauses. It does not inherit the current software default.
    """
    policy = research.candidate_policy
    if policy is not None and policy.policy_version not in KNOWN_PLANNER_REVISIONS:
        return (
            f"未知 planner 修订 {policy.policy_version}，已暂停。"
            "冻结修订保持不变，不会改用当前软件默认值。"
        )
    refs: list[object] = []
    methods = research.brief.round1_methods.value
    if methods:
        refs.extend(methods)
    for version in research.versions:
        for round_ in version.rounds:
            spec = round_.accepted_attempt.spec
            extra = getattr(spec, "method_set", ()) or ()
            refs.extend(extra)
    for ref in refs:
        method_id, revision = _method_revision(ref)
        if not _method_known(store, method_id, revision):
            return (
                f"未知方法修订 {method_id}@{revision}，已暂停。"
                "不会改用另一条修订继续跑。"
            )
    return None


def pause_if_unknown_revision(
    store: SQLiteStore,
    research: Research,
    now: datetime,
) -> Research | None:
    if research.status is not ResearchStatus.RUNNING:
        return None
    reason = revision_pause_reason(store, research)
    if reason is None:
        return None
    paused = transition(research, ResearchEvent.PAUSE, now)
    paused = replace(
        paused,
        last_run_error=reason,
        last_run_error_code="UNKNOWN_REVISION",
    )
    store.save(paused, research.updated_at)
    return paused


def create_upgrade_backup(store: SQLiteStore, dest: Path) -> dict[str, Any]:
    """SQLite consistency backup plus the linked snapshot files."""
    dest.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(store.path)
    try:
        check = source.execute("PRAGMA integrity_check").fetchone()
        if check is None or check[0] != "ok":
            raise RuntimeError(f"sqlite integrity_check failed: {check}")
        database = dest / "research.db"
        if database.exists():
            database.unlink()
        target = sqlite3.connect(database)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    files: list[dict[str, str]] = []
    root = store.path.parent
    ensure_rollout_tables(store)
    rows = store.connection.execute(
        "SELECT relative_path, sha256 FROM frozen_snapshot_seal"
    ).fetchall()
    snapshot_root = dest / "snapshots"
    for relative, digest in rows:
        origin = root / str(relative)
        if not origin.is_file() or _sha256(origin) != str(digest):
            raise RuntimeError(f"refusing to back up a drifted snapshot: {relative}")
        copied = snapshot_root / Path(str(relative)).name
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, copied)
        files.append({"path": Path("snapshots").joinpath(copied.name).as_posix(), "sha256": str(digest)})
    manifest = {
        "database": "research.db",
        "integrity": "ok",
        "files": files,
    }
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def restore_upgrade_backup(backup: Path, temp_dir: Path) -> dict[str, Any]:
    """Restore into a temp data dir and check integrity plus snapshot hashes."""
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    database = temp_dir / "research.db"
    shutil.copy2(backup / "research.db", database)
    restored = sqlite3.connect(database)
    try:
        check = restored.execute("PRAGMA integrity_check").fetchone()
        if check is None or check[0] != "ok":
            raise RuntimeError(f"restored integrity_check failed: {check}")
        receipts = restored.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='command_receipt'"
        ).fetchone()
        if receipts is None or int(receipts[0]) != 1:
            raise RuntimeError("restored database is missing command_receipt")
    finally:
        restored.close()
    checked: list[str] = []
    for item in manifest.get("files") or []:
        relative = str(item["path"])
        expected = str(item["sha256"])
        origin = backup / relative
        copied = temp_dir / Path(relative).name
        shutil.copy2(origin, copied)
        if _sha256(copied) != expected:
            raise RuntimeError(f"restored snapshot hash mismatch: {relative}")
        checked.append(relative)
    store = SQLiteStore(database)
    readable = store.connection.execute("SELECT COUNT(*) FROM researches").fetchone()
    return {
        "integrity": "ok",
        "journal": "command_receipt",
        "researches": int(readable[0]) if readable else 0,
        "files": checked,
    }
