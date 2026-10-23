"""Draft release notes and checksums stay attached to the real installer names."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assemble_release_assets.py"


def _hash_sidecar(path: Path) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")


def test_assemble_release_assets_writes_sums_and_unsigned_notes(tmp_path: Path) -> None:
    deb = tmp_path / "alphaloop_0.9.0_linux_amd64.deb"
    dmg = tmp_path / "alphaloop_0.9.0_macos_arm64.dmg"
    exe = tmp_path / "alphaloop_0.9.0_windows_x64-setup.exe"
    deb.write_bytes(b"deb")
    dmg.write_bytes(b"dmg")
    exe.write_bytes(b"exe")
    for path in (deb, dmg, exe):
        _hash_sidecar(path)
    (tmp_path / "notes.txt").write_text("skip", encoding="utf-8")
    notes = tmp_path / "release-notes.md"
    env = os.environ.copy()
    env["RELEASE_NOTES_PATH"] = str(notes)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path), "0.9.0", "abc123"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    sums = (tmp_path / "SHA256SUMS.txt").read_text(encoding="utf-8")
    assert "alphaloop_0.9.0_linux_amd64.deb" in sums
    assert "alphaloop_0.9.0_macos_arm64.dmg" in sums
    assert "alphaloop_0.9.0_windows_x64-setup.exe" in sums
    assert "notes.txt" not in sums
    body = notes.read_text(encoding="utf-8")
    assert "alphaloop 0.9.0" in body
    assert "`abc123`" in body
    assert "ad-hoc signed" in body
    assert "not notarized" in body
    assert "Open Anyway" in body
    assert "xattr -dr com.apple.quarantine /Applications/alphaloop.app" in body
    assert "sudo apt install ./alphaloop_0.9.0_linux_amd64.deb" in body
    assert "sha256sum -c SHA256SUMS.txt" in body
    assert "WebView2" in body
    assert "synthetic market data" in body
    assert "More info → Run anyway" in body
    assert not (tmp_path / "alphaloop_0.9.0_linux_amd64.deb.sha256").exists()
    assert "| Windows | placeholder |" in body
    assert "| macOS | placeholder |" in body
    assert "| Linux | placeholder |" in body


def test_assemble_release_assets_rejects_a_partial_set(tmp_path: Path) -> None:
    (tmp_path / "alphaloop_0.9.0_linux_amd64.deb").write_bytes(b"deb")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path), "0.9.0", "abc123"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "missing .dmg" in result.stderr
