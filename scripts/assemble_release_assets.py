#!/usr/bin/env python3
"""Build SHA256SUMS.txt and the draft release notes from installer files."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

INSTALLER_SUFFIXES = (".deb", ".dmg", ".exe", ".msi", ".tar.gz")


def installer_files(dist: Path) -> list[Path]:
    files = [
        path
        for path in dist.iterdir()
        if path.is_file() and path.name.endswith(INSTALLER_SUFFIXES)
    ]
    return sorted(files, key=lambda path: path.name)


def sha256_sums(files: list[Path]) -> str:
    lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    return "\n".join(lines) + "\n"


def release_notes(version: str, sha: str) -> str:
    return f"""## alphaloop {version}

Commit: `{sha}`

These builds are **unsigned**.

- **macOS:** Right-click the app and choose Open, or run `xattr -dr com.apple.quarantine` on the `.app` after opening the disk image.
- **Windows:** If SmartScreen appears, choose More info → Run anyway.

## Per-platform test results

| Platform | Result | Notes |
| --- | --- | --- |
| Windows | placeholder | Fill in the CI end-to-end result before publishing. |
| macOS | placeholder | Run the manual checklist in docs/release.md before publishing. |
| Linux | placeholder | Run the manual checklist in docs/release.md before publishing. |
"""


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: assemble_release_assets.py <dist-dir> <version> <sha>", file=sys.stderr)
        return 2
    dist = Path(sys.argv[1])
    version = sys.argv[2]
    sha = sys.argv[3]
    files = installer_files(dist)
    names = [path.name for path in files]
    if not any(name.endswith(".deb") for name in names):
        print(f"missing .deb in {names}", file=sys.stderr)
        return 1
    if not any(name.endswith(".dmg") for name in names):
        print(f"missing .dmg in {names}", file=sys.stderr)
        return 1
    if not any(name.endswith(".exe") or name.endswith(".msi") for name in names):
        print(f"missing Windows installer in {names}", file=sys.stderr)
        return 1
    (dist / "SHA256SUMS.txt").write_text(sha256_sums(files), encoding="utf-8")
    notes_path = Path(os.environ.get("RELEASE_NOTES_PATH", "release-notes.md"))
    notes_path.write_text(release_notes(version, sha), encoding="utf-8")
    print(notes_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
