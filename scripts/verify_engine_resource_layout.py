#!/usr/bin/env python3
"""Verify PyInstaller onedir / staged Tauri engine resource layout (not flattened)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _check_tree(root: Path, label: str) -> None:
    exe = root / "alphaloop-engine"
    internal = root / "_internal"
    if not exe.is_file():
        raise SystemExit(f"{label}: missing executable {exe}")
    if not internal.is_dir():
        raise SystemExit(f"{label}: missing _internal/ under {root}")
    # Flattened bundles put hundreds of files directly under root.
    top_level_files = [p for p in root.iterdir() if p.is_file() and p.name != "alphaloop-engine"]
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
