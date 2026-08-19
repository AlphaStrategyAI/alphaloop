from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from alphaloop.contracts.artifacts import RunLayout

HEARTBEAT_NAME = "heartbeat.json"


@dataclass(frozen=True)
class Checkpoint:
    seq: int
    complete: bool
    payload: dict


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def write_checkpoint(layout: RunLayout, checkpoint: Checkpoint) -> Path:
    layout.checkpoints.mkdir(parents=True, exist_ok=True)
    path = layout.checkpoints / f"ckpt-{checkpoint.seq:06d}.json"
    _atomic_write_json(
        path,
        {
            "seq": checkpoint.seq,
            "complete": checkpoint.complete,
            "payload": checkpoint.payload,
        },
    )
    return path


def load_latest_complete(layout: RunLayout) -> Optional[Checkpoint]:
    if not layout.checkpoints.is_dir():
        return None

    best: Optional[Checkpoint] = None
    for path in layout.checkpoints.glob("ckpt-*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not data.get("complete"):
            continue
        candidate = Checkpoint(
            seq=data["seq"],
            complete=data["complete"],
            payload=data["payload"],
        )
        if best is None or candidate.seq > best.seq:
            best = candidate
    return best


def write_heartbeat(layout: RunLayout, pid: int, at: str) -> Path:
    layout.run_dir.mkdir(parents=True, exist_ok=True)
    path = layout.run_dir / HEARTBEAT_NAME
    _atomic_write_json(path, {"pid": pid, "at": at})
    return path


def read_heartbeat(layout: RunLayout) -> Optional[dict]:
    path = layout.run_dir / HEARTBEAT_NAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
