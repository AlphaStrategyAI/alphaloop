"""Version and git sha baked in by scripts/write_build_info.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def read_build_info() -> tuple[str, str]:
    candidates: list[Path] = []
    bundled = getattr(sys, "_MEIPASS", None)
    if isinstance(bundled, str) and bundled:
        candidates.append(Path(bundled) / "engine" / "research" / "build_info.json")
    candidates.append(Path(__file__).with_name("build_info.json"))
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        version = data.get("version")
        sha = data.get("gitSha")
        if isinstance(version, str) and version and isinstance(sha, str) and sha:
            return version, sha
    return "unknown", "unknown"
