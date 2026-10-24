#!/usr/bin/env python3
"""Fail when the desktop app version declarations disagree.

Included declarations:

- apps/desktop/src-tauri/tauri.conf.json
- apps/desktop/src-tauri/Cargo.toml
- apps/desktop/src-tauri/Cargo.lock (package alphaloop-desktop only)
- apps/desktop/package.json
- apps/desktop/package-lock.json (root and the "" package entry)
- pyproject.toml (shown on the settings about line and in engine.log)
- apps/desktop/src/buildInfo.ts
- engine/research/build_info.json
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def declared_versions(root: Path = ROOT) -> dict[str, str]:
    tauri = json.loads(_read(root / "apps/desktop/src-tauri/tauri.conf.json"))
    package = json.loads(_read(root / "apps/desktop/package.json"))
    lock = json.loads(_read(root / "apps/desktop/package-lock.json"))
    cargo = _read(root / "apps/desktop/src-tauri/Cargo.toml")
    cargo_lock = _read(root / "apps/desktop/src-tauri/Cargo.lock")
    cargo_version = re.search(
        r'(?m)^\[package\]\nname = "alphaloop-desktop"\nversion = "([^"]+)"',
        cargo,
    )
    if cargo_version is None:
        raise SystemExit("Cargo.toml is missing [package] version for alphaloop-desktop")
    lock_version = re.search(
        r'name = "alphaloop-desktop"\nversion = "([^"]+)"',
        cargo_lock,
    )
    if lock_version is None:
        raise SystemExit("Cargo.lock is missing package alphaloop-desktop")
    if lock.get("version") != lock.get("packages", {}).get("", {}).get("version"):
        raise SystemExit("package-lock.json root version and packages[''] version disagree")
    project = tomllib.loads(_read(root / "pyproject.toml"))
    ui = _read(root / "apps" / "desktop" / "src" / "buildInfo.ts")
    ui_version = re.search(r'export const appVersion = "([^"]+)"', ui)
    if ui_version is None:
        raise SystemExit("apps/desktop/src/buildInfo.ts is missing appVersion")
    baked = json.loads(_read(root / "engine" / "research" / "build_info.json"))
    return {
        "tauri.conf.json": str(tauri["version"]),
        "Cargo.toml": cargo_version.group(1),
        "Cargo.lock": lock_version.group(1),
        "package.json": str(package["version"]),
        "package-lock.json": str(lock["version"]),
        "pyproject.toml": str(project["project"]["version"]),
        "buildInfo.ts": ui_version.group(1),
        "build_info.json": str(baked["version"]),
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    versions = declared_versions()
    unique = set(versions.values())
    if len(unique) != 1:
        print("desktop app versions disagree:", file=sys.stderr)
        for name, version in versions.items():
            print(f"  {name}: {version}", file=sys.stderr)
        return 1
    version = next(iter(unique))
    if "--print" in args:
        print(version)
    else:
        print(f"desktop app version {version} is consistent")
        for name in versions:
            print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
