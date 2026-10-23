"""Windows e2e artifacts must not keep auth tokens or typed secrets."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "windows_gui_e2e",
    ROOT / "apps" / "desktop" / "e2e" / "windows_gui_e2e.py",
)
assert SPEC and SPEC.loader
e2e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e2e)


def test_redact_text_replaces_auth_token_and_typed_secrets() -> None:
    raw = '{"auth_token": "super-secret-token", "note": "correct horse"}'
    redacted = e2e.redact_text(raw, ("correct horse",))
    assert "super-secret-token" not in redacted
    assert "correct horse" not in redacted
    assert "[redacted]" in redacted


def test_redacted_tree_fails_if_a_token_remains(tmp_path: Path) -> None:
    log = tmp_path / "engine-direct-stdout.txt"
    log.write_text('{"auth_token": "super-secret-token"}\n', encoding="utf-8")
    e2e.redact_tree(tmp_path)
    assert "super-secret-token" not in log.read_text(encoding="utf-8")
    log.write_text('{"auth_token": "super-secret-token"}\n', encoding="utf-8")
    try:
        e2e.assert_no_secret_leaks(tmp_path)
    except AssertionError as error:
        assert "auth_token" in str(error)
    else:
        raise AssertionError("expected a leak to fail the check")


def test_desktop_handshake_log_does_not_include_the_token() -> None:
    source = (ROOT / "apps" / "desktop" / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
    assert 'alphaloop-engine handshake status={} pid={}' in source
    assert "auth_token" not in source.split("alphaloop-engine handshake status")[1].split("\n", 1)[0]
