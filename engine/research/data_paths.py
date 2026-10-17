from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from platformdirs import user_data_dir

APP_DATA_DIR_NAME = "ai.alphastrategy.alphaloop"


def resolve_data_root(*, ensure_exists: bool = False) -> Path:
    """Persistent user data root (`docs/requirements/paths-contract.md`)."""
    override = os.environ.get("ALPHALOOP_DATA_ROOT")
    if override:
        root = Path(override)
    else:
        root = Path(user_data_dir(APP_DATA_DIR_NAME))
    if ensure_exists:
        root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass(frozen=True, slots=True)
class DataPaths:
    root: Path

    @property
    def database_file(self) -> Path:
        return self.root / "research.db"

    @property
    def engine_log(self) -> Path:
        return self.root / "engine.log"

    @property
    def materials_dir(self) -> Path:
        return self.root / "materials"

    @property
    def exports_dir(self) -> Path:
        return self.root / "exports"

    @property
    def snapshots_dir(self) -> Path:
        return self.root / "snapshots"

    @classmethod
    def default(cls) -> Self:
        return cls(resolve_data_root(ensure_exists=True))
