#!/usr/bin/env python3
"""Build SHA256SUMS.txt and the draft release notes from installer files."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

INSTALLER_SUFFIXES = (".deb", ".dmg", ".exe", ".tar.gz")


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


def verify_build_hashes(dist: Path, files: list[Path]) -> None:
    """Recompute each installer and compare the hash uploaded by its build job."""
    for path in files:
        sidecar = dist / f"{path.name}.sha256"
        if not sidecar.is_file():
            raise SystemExit(f"missing build hash {sidecar.name}")
        recorded = sidecar.read_text(encoding="utf-8").split()[0]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if recorded != actual:
            raise SystemExit(f"hash mismatch for {path.name}: build {recorded} publish {actual}")
        sidecar.unlink()


def release_notes(version: str, sha: str) -> str:
    deb = f"alphaloop_{version}_linux_amd64.deb"
    return f"""## alphaloop {version}

Commit: `{sha}`

## System requirements

- macOS: Apple Silicon only. The build is ad-hoc signed and not notarized.
- Windows: Windows 10 or Windows 11, x64, with the WebView2 runtime.
- Linux: Ubuntu 22.04 or newer.

## Install

- Linux: `sudo apt install ./{deb}`
- Checksums: `sha256sum -c SHA256SUMS.txt`

## Signing

macOS is ad-hoc signed (`codesign` identity `-`) and not notarized. Gatekeeper still warns. On macOS 15 and later, right-click → Open does not bypass that warning. Drag the app to Applications, open it once and let it be blocked, then use System Settings → Privacy & Security → Open Anyway. Testers must download the DMG in a browser from this draft release so the quarantine flag is present. After the app is in Applications, the alternative is `xattr -dr com.apple.quarantine /Applications/alphaloop.app`.

Windows is not Authenticode-signed. If SmartScreen appears, choose More info → Run anyway.

The Linux package is not signed by a distribution key.

## Known limitations

- Windows is tested only by cloud automation.
- That automation uses synthetic market data (`ALPHALOOP_OFFLINE_MARKET_DATA=1`), not Yahoo or Sina.
- macOS is ad-hoc signed and not notarized. Linux and Windows builds are unsigned.

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
    if not any(name.endswith("-setup.exe") for name in names):
        print(f"missing Windows NSIS setup in {names}", file=sys.stderr)
        return 1
    verify_build_hashes(dist, files)
    (dist / "SHA256SUMS.txt").write_text(sha256_sums(files), encoding="utf-8")
    notes_path = Path(os.environ.get("RELEASE_NOTES_PATH", "release-notes.md"))
    notes_path.write_text(release_notes(version, sha), encoding="utf-8")
    print(notes_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
