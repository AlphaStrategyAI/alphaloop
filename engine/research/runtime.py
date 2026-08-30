from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

import portalocker
from platformdirs import user_runtime_path

OwnerKind = Literal["desktop", "cli"]


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    root: Path
    lock_file: Path
    owner_file: Path

    @property
    def database_file(self) -> Path:
        return self.root / "research.db"

    @property
    def engine_log(self) -> Path:
        return self.root / "engine.log"

    @classmethod
    def default(cls) -> Self:
        root = Path(user_runtime_path("alphaloop", ensure_exists=True))
        return cls(root, root / "engine.lock", root / "owner.json")


@dataclass(frozen=True, slots=True)
class OwnerRecord:
    owner: OwnerKind
    pid: int
    started_at: str
    phase: Literal["starting", "ready"] = "starting"
    endpoint: str | None = None
    auth_token: str | None = None


@dataclass(slots=True)
class EngineLock:
    paths: RuntimePaths
    owner: OwnerRecord
    _handle: object

    @classmethod
    def acquire(cls, paths: RuntimePaths, owner: OwnerKind) -> Self:
        paths.root.mkdir(parents=True, exist_ok=True)
        handle = open(paths.lock_file, "a+", encoding="utf-8")  # noqa: SIM115
        try:
            portalocker.lock(handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except portalocker.LockException:
            handle.close()
            raise RuntimeError("alphaloop engine already has an owner")
        record = OwnerRecord(owner, os.getpid(), datetime.now(UTC).isoformat())
        temporary = paths.owner_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(record), sort_keys=True), encoding="utf-8")
        os.replace(temporary, paths.owner_file)
        return cls(paths, record, handle)

    def close(self) -> None:
        if not getattr(self._handle, "closed", True):
            portalocker.unlock(self._handle)  # type: ignore[arg-type]
            self._handle.close()  # type: ignore[attr-defined]
        self.paths.owner_file.unlink(missing_ok=True)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def read_live_owner(paths: RuntimePaths) -> OwnerRecord | None:
    if not paths.owner_file.exists():
        return None
    probe = open(paths.lock_file, "a+", encoding="utf-8")  # noqa: SIM115
    try:
        portalocker.lock(probe, portalocker.LOCK_EX | portalocker.LOCK_NB)
    except portalocker.LockException:
        payload = json.loads(paths.owner_file.read_text(encoding="utf-8"))
        return OwnerRecord(**payload)
    else:
        portalocker.unlock(probe)
        paths.owner_file.unlink(missing_ok=True)
        return None
    finally:
        probe.close()


def publish_ready(
    lock: EngineLock,
    endpoint: str,
    auth_token: str,
) -> OwnerRecord:
    ready = replace(
        lock.owner,
        phase="ready",
        endpoint=endpoint,
        auth_token=auth_token,
    )
    temporary = lock.paths.owner_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(ready), sort_keys=True), encoding="utf-8")
    os.replace(temporary, lock.paths.owner_file)
    lock.owner = ready
    return ready
