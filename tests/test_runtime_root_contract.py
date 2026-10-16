"""Cross-language runtime root contract (`docs/requirements/runtime-root.md`)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from engine.research.runtime import resolve_runtime_root

FIXTURES: list[tuple[dict[str, str | None], str]] = [
    (
        {"ALPHALOOP_RUNTIME_ROOT": "/tmp/alphaloop-py-contract", "XDG_RUNTIME_DIR": None},
        "/tmp/alphaloop-py-contract",
    ),
]


def _apply_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str | None]) -> None:
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


@pytest.mark.parametrize("env,expected_root", FIXTURES)
def test_python_resolve_runtime_root(monkeypatch: pytest.MonkeyPatch, env: dict[str, str | None], expected_root: str) -> None:
    _apply_env(monkeypatch, env)
    assert resolve_runtime_root() == Path(expected_root)


def test_python_matches_platformdirs_without_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHALOOP_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    from platformdirs import user_runtime_path

    assert resolve_runtime_root() == Path(user_runtime_path("alphaloop", ensure_exists=False))


def test_rust_engine_paths_tests_cover_contract() -> None:
    tauri_dir = Path("apps/desktop/src-tauri")
    proc = subprocess.run(
        ["cargo", "test", "-q", "engine_paths::tests", "--", "--nocapture"],
        cwd=tauri_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_runtime_root_contract_doc_exists() -> None:
    doc = Path("docs/requirements/runtime-root.md").read_text(encoding="utf-8")
    assert "ALPHALOOP_RUNTIME_ROOT" in doc
    assert "runtime-<uid>" in doc
