"""The sidecar install lock pins PyInstaller and carries hashes."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "packaging" / "requirements-sidecar.txt"


def test_sidecar_requirements_pin_pyinstaller_with_hashes() -> None:
    text = LOCK.read_text(encoding="utf-8")
    assert "\npyinstaller==" in f"\n{text}"
    assert "\nsetuptools==" in f"\n{text}"
    assert "--hash=sha256:" in text
    assert "via -r packaging/requirements-sidecar.in" in text
