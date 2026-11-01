"""Round commit, step ledger, and effective-time slices on SQLiteStore."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from engine.research.models import Attempt, MethodRef, Research
from engine.research.user_errors import UserFacingError

LOCAL_COMMIT_ATTEMPTS = 3


def guarded_billed_call(
    store: object,
    *,
    research_id: str,
    version: int,
    round_number: int,
    attempt: int,
    step: str,
    input_hash: str,
    call: Any,
    idempotent: bool = False,
    authorize: bool = False,
) -> Any:
    """Send a paid call at most once unless the provider is idempotent or the user authorizes another."""
    status, result_ref = store.claim_step(  # type: ignore[attr-defined]
        research_id,
        version,
        round_number,
        attempt,
        step,
        input_hash,
        billed=True,
    )
    if status == "done":
        return result_ref
    if status == "unknown" and not authorize and not idempotent:
        raise UserFacingError(
            "REMOTE_UNKNOWN_NEEDS_AUTH",
            "这次付费调用未能确认是否已经发出，需要你授权后才能重试。",
        )
    if status == "unknown":
        store.reopen_billed_step(  # type: ignore[attr-defined]
            research_id,
            version,
            round_number,
            attempt,
            step,
            input_hash,
        )
    try:
        value = call()
    except Exception:
        store.mark_step_unknown(  # type: ignore[attr-defined]
            research_id,
            version,
            round_number,
            attempt,
            step,
            input_hash,
        )
        raise
    store.complete_step(  # type: ignore[attr-defined]
        research_id,
        version,
        round_number,
        attempt,
        step,
        input_hash,
        str(value),
    )
    return value


def candidate_hash(spec: object, frozen_hash: str) -> str:
    """Identity of one executable candidate. Attempt id and prose are excluded."""
    payload = {
        "model_family": getattr(spec, "model_family", ""),
        "lookback_days": getattr(spec, "lookback_days", None),
        "entry_z": getattr(spec, "entry_z", None),
        "side": getattr(spec, "side", ""),
        "max_drawdown_floor": getattr(spec, "max_drawdown_floor", None),
        "cost_model": getattr(spec, "cost_model", ""),
        "strategy_family": getattr(spec, "strategy_family", ""),
        "family_method": getattr(spec, "family_method", ""),
        "primary_factor": getattr(spec, "primary_factor", None),
        "frozen": frozen_hash,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    import hashlib

    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class RoundReplay(Exception):
    """This round or candidate was already committed. The caller reloads it."""


@dataclass(frozen=True, slots=True)
class RoundDecision:
    kind: str
    round_id: str | None = None
    attempt_id: str | None = None
    version_number: int | None = None
    round_number: int | None = None
    window_key: str | None = None
    method_refs: tuple[MethodRef, ...] = ()
    csv_fingerprint: str = ""
    candidate_hash: str = ""


ROUND_RECOVERY_SCHEMA = """
CREATE TABLE IF NOT EXISTS step_run (
    research_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    round INTEGER NOT NULL,
    attempt INTEGER NOT NULL,
    step TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    result_ref TEXT,
    billed INTEGER NOT NULL DEFAULT 0,
    budget_reserved INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (research_id, version, round, attempt, step, input_hash)
);
CREATE TABLE IF NOT EXISTS committed_round (
    research_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    round_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    candidate_hash TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (research_id, version_number, round_number)
);
CREATE TABLE IF NOT EXISTS committed_candidate (
    research_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    candidate_hash TEXT NOT NULL,
    round_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    PRIMARY KEY (research_id, version_number, candidate_hash)
);
CREATE TABLE IF NOT EXISTS window_round_ledger (
    research_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    round_id TEXT NOT NULL,
    window_key TEXT NOT NULL,
    PRIMARY KEY (research_id, version_number, round_number)
);
CREATE TABLE IF NOT EXISTS round_receipt (
    research_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    round_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (research_id, version_number, round_number)
);
CREATE TABLE IF NOT EXISTS compute_lease (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    research_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS seen_market_interval (
    interval_id TEXT PRIMARY KEY,
    market TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    research_id TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS holdout_evaluation (
    window_key TEXT PRIMARY KEY,
    candidate_fingerprint TEXT NOT NULL,
    research_id TEXT NOT NULL,
    status TEXT NOT NULL,
    result_ref TEXT
);
CREATE INDEX IF NOT EXISTS idx_step_run_research
    ON step_run(research_id, version, round);
"""


class RoundRecoveryMixin:
    connection: Any
    path: Any

    def _migrate_round_recovery(self) -> None:
        self._ensure_column(  # type: ignore[attr-defined]
            "researches",
            "effective_seconds_ledger",
            "effective_seconds_ledger REAL NOT NULL DEFAULT 0",
        )
        self.connection.executescript(ROUND_RECOVERY_SCHEMA)
        self._recover_pending_billed_steps()

    def _recover_pending_billed_steps(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE step_run
                   SET status='unknown',
                       budget_reserved=CASE WHEN budget_reserved > 0 THEN budget_reserved ELSE 1 END
                 WHERE status='pending' AND billed=1
                """
            )

    def add_effective_slice(self, research_id: str, seconds: float) -> None:
        if seconds <= 0:
            return
        with self.connection:
            self.connection.execute(
                """
                UPDATE researches
                   SET effective_seconds_ledger = effective_seconds_ledger + ?
                 WHERE research_id=?
                """,
                (float(seconds), research_id),
            )

    def effective_seconds_ledger(self, research_id: str) -> float:
        row = self.connection.execute(
            "SELECT effective_seconds_ledger FROM researches WHERE research_id=?",
            (research_id,),
        ).fetchone()
        if row is None or row[0] is None:
            return 0.0
        return float(row[0])

    def try_acquire_worker(self, research_id: str) -> bool:
        with self.connection:
            row = self.connection.execute(
                "SELECT research_id FROM compute_lease WHERE singleton=1"
            ).fetchone()
            if row is None:
                self.connection.execute(
                    "INSERT INTO compute_lease(singleton, research_id) VALUES(1, ?)",
                    (research_id,),
                )
                return True
            return str(row[0]) == research_id

    def release_worker(self, research_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM compute_lease WHERE singleton=1 AND research_id=?",
                (research_id,),
            )

    def claim_step(
        self,
        research_id: str,
        version: int,
        round_number: int,
        attempt: int,
        step: str,
        input_hash: str,
        *,
        billed: bool = False,
    ) -> tuple[str, str | None]:
        with self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO step_run(
                    research_id, version, round, attempt, step, input_hash,
                    status, result_ref, billed, budget_reserved
                ) VALUES(?,?,?,?,?,?, 'pending', NULL, ?, ?)
                """,
                (
                    research_id,
                    version,
                    round_number,
                    attempt,
                    step,
                    input_hash,
                    int(billed),
                    1 if billed else 0,
                ),
            )
            row = self.connection.execute(
                """
                SELECT status, result_ref FROM step_run
                 WHERE research_id=? AND version=? AND round=? AND attempt=?
                   AND step=? AND input_hash=?
                """,
                (research_id, version, round_number, attempt, step, input_hash),
            ).fetchone()
        if row is None:
            return ("pending", None)
        return (str(row[0]), None if row[1] is None else str(row[1]))

    def complete_step(
        self,
        research_id: str,
        version: int,
        round_number: int,
        attempt: int,
        step: str,
        input_hash: str,
        result_ref: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE step_run
                   SET status='done', result_ref=?
                 WHERE research_id=? AND version=? AND round=? AND attempt=?
                   AND step=? AND input_hash=?
                """,
                (result_ref, research_id, version, round_number, attempt, step, input_hash),
            )

    def mark_step_unknown(
        self,
        research_id: str,
        version: int,
        round_number: int,
        attempt: int,
        step: str,
        input_hash: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE step_run
                   SET status='unknown',
                       budget_reserved=CASE WHEN budget_reserved > 0 THEN budget_reserved ELSE 1 END
                 WHERE research_id=? AND version=? AND round=? AND attempt=?
                   AND step=? AND input_hash=?
                """,
                (research_id, version, round_number, attempt, step, input_hash),
            )

    def reopen_billed_step(
        self,
        research_id: str,
        version: int,
        round_number: int,
        attempt: int,
        step: str,
        input_hash: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE step_run
                   SET status='pending'
                 WHERE research_id=? AND version=? AND round=? AND attempt=?
                   AND step=? AND input_hash=?
                """,
                (research_id, version, round_number, attempt, step, input_hash),
            )

    def billed_budget(self, research_id: str) -> int:
        row = self.connection.execute(
            """
            SELECT COALESCE(SUM(budget_reserved), 0) FROM step_run
             WHERE research_id=? AND billed=1
            """,
            (research_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    def step_rows(self, research_id: str) -> tuple[tuple[Any, ...], ...]:
        rows = self.connection.execute(
            """
            SELECT version, round, attempt, step, input_hash, status, result_ref, billed
              FROM step_run WHERE research_id=?
             ORDER BY version, round, attempt, step
            """,
            (research_id,),
        ).fetchall()
        return tuple(tuple(row) for row in rows)

    def latest_passed_attempt(
        self,
        research_id: str,
        version_number: int,
        round_number: int,
    ) -> Attempt | None:
        from engine.research.store import CONVERTER

        row = self.connection.execute(
            """
            SELECT attempt_json FROM review_attempts
             WHERE research_id=? AND version_number=? AND round_number=? AND passed=1
             ORDER BY created_at DESC LIMIT 1
            """,
            (research_id, version_number, round_number),
        ).fetchone()
        if row is None:
            return None
        return CONVERTER.structure(json.loads(row[0]), Attempt)

    def research_id_for_create_command(self, command_id: str) -> str | None:
        row = self.connection.execute(
            "SELECT research_id FROM researches WHERE create_command_id=?",
            (command_id,),
        ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def commit_round_decision(
        self,
        research: Research,
        *,
        expected_updated_at: datetime,
        expected_revision: int,
        decision: RoundDecision,
    ) -> int:
        from engine.research.e2e_hooks import maybe_raise_busy

        last_busy: sqlite3.OperationalError | None = None
        for _attempt in range(LOCAL_COMMIT_ATTEMPTS):
            try:
                return self._commit_round_once(
                    research,
                    expected_updated_at=expected_updated_at,
                    expected_revision=expected_revision,
                    decision=decision,
                    raise_busy=maybe_raise_busy,
                )
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                    raise
                last_busy = exc
        raise UserFacingError(
            "DB_BUSY",
            "数据库正忙，这一步已停下，可以恢复。",
        ) from last_busy

    def _commit_round_once(
        self,
        research: Research,
        *,
        expected_updated_at: datetime,
        expected_revision: int,
        decision: RoundDecision,
        raise_busy: Any,
    ) -> int:
        from engine.research.store import ConcurrentWrite

        with self.connection:
            raise_busy()
            if decision.round_id is not None and decision.version_number and decision.round_number:
                existing = self.connection.execute(
                    """
                    SELECT round_id FROM committed_round
                     WHERE research_id=? AND version_number=? AND round_number=?
                    """,
                    (research.research_id, decision.version_number, decision.round_number),
                ).fetchone()
                if existing is not None:
                    raise RoundReplay()
            if decision.candidate_hash and decision.version_number:
                existing_candidate = self.connection.execute(
                    """
                    SELECT round_id FROM committed_candidate
                     WHERE research_id=? AND version_number=? AND candidate_hash=?
                    """,
                    (research.research_id, decision.version_number, decision.candidate_hash),
                ).fetchone()
                if existing_candidate is not None:
                    raise RoundReplay()
            row = self.connection.execute(
                """
                SELECT revision, last_seq FROM researches
                 WHERE research_id=? AND updated_at=? AND revision=?
                """,
                (
                    research.research_id,
                    expected_updated_at.isoformat(),
                    expected_revision,
                ),
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
                    self._encode(research),  # type: ignore[attr-defined]
                    research.updated_at.isoformat(),
                    completed,
                    research.status.value,
                    revision,
                    seq,
                    research.research_id,
                    expected_updated_at.isoformat(),
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise ConcurrentWrite(research.research_id)
            self.connection.execute(
                """
                INSERT INTO research_event(
                    research_id, seq, version, kind, refs_json, created_at
                ) VALUES(?,?,?,?,?,?)
                """,
                (
                    research.research_id,
                    seq,
                    research.current_version_number,
                    decision.kind,
                    json.dumps(
                        {
                            "round_id": decision.round_id,
                            "attempt_id": decision.attempt_id,
                            "candidate_hash": decision.candidate_hash,
                            "csv_fingerprint": decision.csv_fingerprint,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    research.updated_at.isoformat(),
                ),
            )
            for item in decision.method_refs:
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO method_usage(
                        method_id, revision_hash, research_id, version_number
                    ) VALUES(?,?,?,?)
                    """,
                    (
                        item.method_id,
                        item.revision_hash,
                        research.research_id,
                        decision.version_number or research.current_version_number or 0,
                    ),
                )
            if (
                decision.window_key
                and decision.round_id
                and decision.version_number
                and decision.round_number
            ):
                inserted = self.connection.execute(
                    """
                    INSERT OR IGNORE INTO window_round_ledger(
                        research_id, version_number, round_number, round_id, window_key
                    ) VALUES(?,?,?,?,?)
                    """,
                    (
                        research.research_id,
                        decision.version_number,
                        decision.round_number,
                        decision.round_id,
                        decision.window_key,
                    ),
                )
                if inserted.rowcount == 1:
                    current = self.connection.execute(
                        "SELECT cumulative_rounds FROM data_window_round_counts WHERE window_key=?",
                        (decision.window_key,),
                    ).fetchone()
                    next_count = (int(current[0]) if current is not None else 0) + 1
                    self.connection.execute(
                        """
                        INSERT INTO data_window_round_counts(window_key, cumulative_rounds)
                        VALUES(?, ?)
                        ON CONFLICT(window_key) DO UPDATE SET
                            cumulative_rounds=excluded.cumulative_rounds
                        """,
                        (decision.window_key, next_count),
                    )
            if decision.round_id and decision.version_number and decision.round_number:
                self.connection.execute(
                    """
                    INSERT INTO committed_round(
                        research_id, version_number, round_number, round_id, attempt_id, candidate_hash
                    ) VALUES(?,?,?,?,?,?)
                    """,
                    (
                        research.research_id,
                        decision.version_number,
                        decision.round_number,
                        decision.round_id,
                        decision.attempt_id or "",
                        decision.candidate_hash,
                    ),
                )
            if decision.candidate_hash and decision.version_number and decision.round_id:
                self.connection.execute(
                    """
                    INSERT INTO committed_candidate(
                        research_id, version_number, candidate_hash, round_id, attempt_id
                    ) VALUES(?,?,?,?,?)
                    """,
                    (
                        research.research_id,
                        decision.version_number,
                        decision.candidate_hash,
                        decision.round_id,
                        decision.attempt_id or "",
                    ),
                )
            return revision

    def write_round_receipt(
        self,
        research: Research,
        decision: RoundDecision,
        revision: int,
    ) -> dict[str, Any]:
        if decision.version_number is None or decision.round_number is None or decision.round_id is None:
            return {}
        window_m = 0
        if decision.window_key:
            row = self.connection.execute(
                "SELECT cumulative_rounds FROM data_window_round_counts WHERE window_key=?",
                (decision.window_key,),
            ).fetchone()
            window_m = int(row[0]) if row is not None else 0
        else:
            window_m = sum(len(version.rounds) for version in research.versions)
        payload = {
            "research_id": research.research_id,
            "round_id": decision.round_id,
            "attempt_id": decision.attempt_id or "",
            "csv_fingerprint": decision.csv_fingerprint,
            "window_m": window_m,
            "effective_seconds": research.effective_seconds,
            "revision": revision,
            "candidate_hash": decision.candidate_hash,
            "status": research.status.value,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO round_receipt(
                    research_id, version_number, round_number, round_id, payload_json
                ) VALUES(?,?,?,?,?)
                """,
                (
                    research.research_id,
                    decision.version_number,
                    decision.round_number,
                    decision.round_id,
                    encoded,
                ),
            )
        return self.round_receipt(research.research_id, decision.version_number, decision.round_number) or payload

    def round_receipt(
        self,
        research_id: str,
        version_number: int,
        round_number: int,
    ) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT payload_json FROM round_receipt
             WHERE research_id=? AND version_number=? AND round_number=?
            """,
            (research_id, version_number, round_number),
        ).fetchone()
        if row is None:
            return None
        parsed = json.loads(row[0])
        return parsed if isinstance(parsed, dict) else None

    def note_seen_interval(
        self,
        *,
        interval_id: str,
        market: str,
        start_date: str,
        end_date: str,
        research_id: str,
        source_fingerprint: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO seen_market_interval(
                    interval_id, market, start_date, end_date, research_id, source_fingerprint
                ) VALUES(?,?,?,?,?,?)
                """,
                (interval_id, market, start_date, end_date, research_id, source_fingerprint),
            )

    def seen_intervals(self, market: str) -> tuple[tuple[str, str, str], ...]:
        rows = self.connection.execute(
            """
            SELECT start_date, end_date, research_id FROM seen_market_interval
             WHERE market=? ORDER BY start_date, end_date
            """,
            (market,),
        ).fetchall()
        return tuple((str(row[0]), str(row[1]), str(row[2])) for row in rows)

    def claim_holdout_evaluation(
        self,
        window_key: str,
        candidate_fingerprint: str,
        research_id: str,
    ) -> str:
        """Return ``claimed``, ``replay``, or ``rejected``."""
        with self.connection:
            row = self.connection.execute(
                """
                SELECT candidate_fingerprint, status FROM holdout_evaluation
                 WHERE window_key=?
                """,
                (window_key,),
            ).fetchone()
            if row is None:
                self.connection.execute(
                    """
                    INSERT INTO holdout_evaluation(
                        window_key, candidate_fingerprint, research_id, status, result_ref
                    ) VALUES(?,?,?,'claimed','')
                    """,
                    (window_key, candidate_fingerprint, research_id),
                )
                return "claimed"
            if str(row[0]) == candidate_fingerprint:
                return "replay"
            return "rejected"

    def list_heads(self) -> tuple[tuple[str, str, int, int], ...]:
        rows = self.connection.execute(
            """
            SELECT research_id, status, revision, last_seq
              FROM researches
             ORDER BY updated_at DESC
            """
        ).fetchall()
        return tuple((str(row[0]), str(row[1]), int(row[2]), int(row[3])) for row in rows)
