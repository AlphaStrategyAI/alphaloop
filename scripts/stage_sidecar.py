from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def stage(target: str, source: Path, tauri_root: Path) -> None:
    executable_name = "alphaloop-engine.exe" if "windows" in target else "alphaloop-engine"
    source_executable = source / executable_name
    if not source_executable.is_file():
        raise FileNotFoundError(source_executable)
    destination = tauri_root / "resources" / "engine"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    staged_executable = destination / executable_name
    staged_executable.chmod(staged_executable.stat().st_mode | 0o111)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--source", type=Path, default=Path("dist/alphaloop-engine"))
    parser.add_argument(
        "--tauri-root",
        type=Path,
        default=Path("apps/desktop/src-tauri"),
    )
    args = parser.parse_args()
    stage(args.target, args.source, args.tauri_root)


if __name__ == "__main__":
    main()
