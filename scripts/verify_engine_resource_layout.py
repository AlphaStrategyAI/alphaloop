#!/usr/bin/env python3
"""Verify PyInstaller onedir / staged Tauri engine resource layout (not flattened)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


_ENGINE_NAMES = ("alphaloop-engine", "alphaloop-engine.exe")


def _find_engine_executable(root: Path) -> Path:
    for name in _ENGINE_NAMES:
        candidate = root / name
        if candidate.is_file():
            return candidate
    raise SystemExit(f"missing executable under {root} (tried {_ENGINE_NAMES})")


def _check_tree(root: Path, label: str) -> None:
    exe = _find_engine_executable(root)
    internal = root / "_internal"
    if not internal.is_dir():
        raise SystemExit(f"{label}: missing _internal/ under {root}")
    # Flattened bundles put hundreds of files directly under root.
    allowed = set(_ENGINE_NAMES)
    top_level_files = [p for p in root.iterdir() if p.is_file() and p.name not in allowed]
    if len(top_level_files) > 5:
        raise SystemExit(
            f"{label}: looks flattened ({len(top_level_files)} extra files at top level)"
        )
    print(json.dumps({"ok": True, "label": label, "root": str(root)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, help="PyInstaller dist/alphaloop-engine")
    parser.add_argument("--staged", type=Path, help="src-tauri/resources/engine/alphaloop-engine")
    args = parser.parse_args()
    conf = Path("apps/desktop/src-tauri/tauri.conf.json")
    if conf.is_file():
        data = json.loads(conf.read_text(encoding="utf-8"))
        resources = data.get("bundle", {}).get("resources", {})
        if any("**/*" in str(k) for k in resources):
            raise SystemExit("tauri.conf.json must not use **/* glob for engine onedir")
        if resources.get("resources/engine/alphaloop-engine") != "engine/alphaloop-engine":
            raise SystemExit(
                "tauri.conf.json must map directory resources/engine/alphaloop-engine"
            )
    if args.source:
        _check_tree(args.source, "pyinstaller-dist")
    if args.staged:
        _check_tree(args.staged, "tauri-staged")


if __name__ == "__main__":
    main()
