from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from alphaloop.contracts.research_spec import ResearchSpec
from alphaloop.contracts.status import JobStatus, ResearchOutcome, derive_research_outcome


def new_run_id() -> str:
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    return f"j_{stamp}_{secrets.token_hex(4)}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class JobRecord:
    run_id: str
    status: JobStatus
    research_outcome: ResearchOutcome
    spec: ResearchSpec
    created_at: str
    updated_at: str
    worker_pid: Optional[int]
    heartbeat_at: Optional[str]
    error: Optional[str]
    sealed_outcome: Optional[ResearchOutcome]
    recovery_attempts: int


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
  run_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  research_outcome TEXT NOT NULL,
  spec_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  worker_pid INTEGER,
  error TEXT,
  sealed_outcome TEXT,
  recovery_attempts INTEGER NOT NULL DEFAULT 0,
  heartbeat_at TEXT
)
"""


class JobStore:
    def __init__(self, db_path: Path, data_dir: Path) -> None:
        self._db_path = db_path
        self._data_dir = data_dir
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_record(self, row: sqlite3.Row) -> JobRecord:
        sealed_raw = row["sealed_outcome"]
        sealed = ResearchOutcome(sealed_raw) if sealed_raw is not None else None
        return JobRecord(
            run_id=row["run_id"],
            status=JobStatus(row["status"]),
            research_outcome=ResearchOutcome(row["research_outcome"]),
            spec=ResearchSpec.from_dict(json.loads(row["spec_json"])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            worker_pid=row["worker_pid"],
            heartbeat_at=row["heartbeat_at"],
            error=row["error"],
            sealed_outcome=sealed,
            recovery_attempts=row["recovery_attempts"],
        )

    def create(self, spec: ResearchSpec, run_id: Optional[str] = None) -> JobRecord:
        rid = run_id or new_run_id()
        now = _utc_now_iso()
        run_dir = self._data_dir / rid
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "checkpoints").mkdir(exist_ok=True)
        spec_path = run_dir / "research-spec.yaml"
        spec_path.write_text(
            yaml.safe_dump(spec.to_dict(), sort_keys=True),
            encoding="utf-8",
        )
        spec_json = json.dumps(spec.to_dict())
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO jobs (
                      run_id, status, research_outcome, spec_json,
                      created_at, updated_at, recovery_attempts
                    ) VALUES (?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        rid,
                        JobStatus.QUEUED.value,
                        ResearchOutcome.NONE.value,
                        spec_json,
                        now,
                        now,
                    ),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM jobs WHERE run_id = ?", (rid,)
                ).fetchone()
        return self._row_to_record(row)

    def get(self, run_id: str) -> JobRecord:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM jobs WHERE run_id = ?", (run_id,)
                ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return self._row_to_record(row)

    def list_jobs(self) -> tuple[JobRecord, ...]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at"
                ).fetchall()
        return tuple(self._row_to_record(row) for row in rows)

    def update_status(
        self,
        run_id: str,
        status: JobStatus,
        *,
        error: Optional[str] = None,
        worker_pid: Optional[int] = None,
    ) -> JobRecord:
        now = _utc_now_iso()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM jobs WHERE run_id = ?", (run_id,)
                ).fetchone()
                if row is None:
                    raise KeyError(run_id)
                sealed_raw = row["sealed_outcome"]
                sealed = (
                    ResearchOutcome(sealed_raw) if sealed_raw is not None else None
                )
                outcome = derive_research_outcome(
                    status,
                    evidence_complete=False,
                    all_gates_passed=False,
                    sealed=sealed,
                )
                if worker_pid is not None:
                    conn.execute(
                        """
                        UPDATE jobs SET
                          status = ?, research_outcome = ?, updated_at = ?,
                          error = ?, worker_pid = ?
                        WHERE run_id = ?
                        """,
                        (
                            status.value,
                            outcome.value,
                            now,
                            error,
                            worker_pid,
                            run_id,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE jobs SET
                          status = ?, research_outcome = ?, updated_at = ?,
                          error = ?
                        WHERE run_id = ?
                        """,
                        (
                            status.value,
                            outcome.value,
                            now,
                            error,
                            run_id,
                        ),
                    )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM jobs WHERE run_id = ?", (run_id,)
                ).fetchone()
        return self._row_to_record(row)

    def requeue_unless_terminal(self, run_id: str) -> JobRecord:
        now = _utc_now_iso()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM jobs WHERE run_id = ?", (run_id,)
                ).fetchone()
                if row is None:
                    raise KeyError(run_id)
                status = JobStatus(row["status"])
                if status in (JobStatus.CANCELLED, JobStatus.COMPLETED):
                    raise ValueError(f"cannot resume {status.value} job")
                conn.execute(
                    """
                    UPDATE jobs SET
                      status = ?, research_outcome = ?, updated_at = ?,
                      error = NULL, worker_pid = NULL
                    WHERE run_id = ?
                    """,
                    (
                        JobStatus.QUEUED.value,
                        ResearchOutcome.NONE.value,
                        now,
                        run_id,
                    ),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM jobs WHERE run_id = ?", (run_id,)
                ).fetchone()
        return self._row_to_record(row)

    def set_heartbeat(self, run_id: str, *, pid: int, at: str) -> JobRecord:
        now = _utc_now_iso()
        with self._lock:
            with self._connect() as conn:
                result = conn.execute(
                    """
                    UPDATE jobs SET worker_pid = ?, heartbeat_at = ?, updated_at = ?
                    WHERE run_id = ?
                    """,
                    (pid, at, now, run_id),
                )
                if result.rowcount == 0:
                    raise KeyError(run_id)
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM jobs WHERE run_id = ?", (run_id,)
                ).fetchone()
        return self._row_to_record(row)

    def increment_recovery(self, run_id: str) -> JobRecord:
        now = _utc_now_iso()
        with self._lock:
            with self._connect() as conn:
                result = conn.execute(
                    """
                    UPDATE jobs SET
                      recovery_attempts = recovery_attempts + 1, updated_at = ?
                    WHERE run_id = ?
                    """,
                    (now, run_id),
                )
                if result.rowcount == 0:
                    raise KeyError(run_id)
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM jobs WHERE run_id = ?", (run_id,)
                ).fetchone()
        return self._row_to_record(row)
