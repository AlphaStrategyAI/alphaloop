"""Draft release notes and checksums stay attached to the real installer names."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assemble_release_assets.py"


def test_assemble_release_assets_writes_sums_and_unsigned_notes(tmp_path: Path) -> None:
    (tmp_path / "alphaloop_0.9.0_linux_amd64.deb").write_bytes(b"deb")
    (tmp_path / "alphaloop_0.9.0_macos_arm64.dmg").write_bytes(b"dmg")
    (tmp_path / "alphaloop_0.9.0_windows_x64-setup.exe").write_bytes(b"exe")
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
    assert "unsigned" in body
    assert "xattr -dr com.apple.quarantine" in body
    assert "More info → Run anyway" in body
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
