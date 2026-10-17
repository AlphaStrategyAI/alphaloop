from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATION_MARKER = ".migrated-from-runtime-root"
LEGACY_DATA_DIRS = ("materials", "exports", "snapshots")


def migrate_legacy_runtime_data(runtime_root: Path, data_root: Path) -> bool:
    """Copy persistent data from pre-split runtime layout into the data root.

    Never deletes legacy files. Writes a marker after a successful DB copy.
    Returns True if any migration step ran.
    """
    marker = data_root / MIGRATION_MARKER
    if marker.exists():
        return False

    data_root.mkdir(parents=True, exist_ok=True)
    migrated = False

    legacy_db = runtime_root / "research.db"
    target_db = data_root / "research.db"
    if not target_db.exists() and legacy_db.is_file():
        shutil.copy2(legacy_db, target_db)
        if target_db.stat().st_size < legacy_db.stat().st_size:
            target_db.unlink(missing_ok=True)
            raise RuntimeError(
                f"research.db migration verification failed ({runtime_root} -> {data_root})"
            )
        logger.info(
            "migrated research.db from runtime dir %s to data dir %s",
            runtime_root,
            data_root,
        )
        migrated = True

    for dirname in LEGACY_DATA_DIRS:
        src = runtime_root / dirname
        dst = data_root / dirname
        if src.is_dir() and not dst.exists():
            shutil.copytree(src, dst)
            logger.info("migrated %s/ from %s to %s", dirname, runtime_root, data_root)
            migrated = True

    if migrated:
        marker.write_text(
            json.dumps({"from_runtime_root": str(runtime_root)}, sort_keys=True),
            encoding="utf-8",
        )
        return True
    return False
