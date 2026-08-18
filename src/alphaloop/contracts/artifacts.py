from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


class DatasetMismatchError(ValueError):
    """Raised when snapshot bytes do not match the recorded hash."""


@dataclass(frozen=True)
class DatasetRef:
    dataset_id: str
    sha256: str


@dataclass(frozen=True)
class RunLayout:
    run_dir: Path

    @property
    def research_spec(self) -> Path:
        return self.run_dir / "research-spec.yaml"

    @property
    def manifest(self) -> Path:
        return self.run_dir / "manifest.yaml"

    @property
    def trial_ledger(self) -> Path:
        return self.run_dir / "trial-ledger.jsonl"

    @property
    def checkpoints(self) -> Path:
        return self.run_dir / "checkpoints"

    @property
    def candidates(self) -> Path:
        return self.run_dir / "candidates.parquet"

    @property
    def evidence(self) -> Path:
        return self.run_dir / "evidence"

    @property
    def recommendations(self) -> Path:
        return self.run_dir / "recommendations.json"

    @property
    def report(self) -> Path:
        return self.run_dir / "report.md"


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_dataset(ref: DatasetRef, blob: bytes) -> None:
    digest = hash_bytes(blob)
    if digest != ref.sha256:
        raise DatasetMismatchError(
            f"dataset {ref.dataset_id} hash mismatch: expected {ref.sha256}, got {digest}"
        )
