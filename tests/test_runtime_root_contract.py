"""Cross-language runtime root contract (`docs/requirements/runtime-root.md`)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from engine.research.runtime import resolve_runtime_root
from engine.research.runtime_contract import resolve_runtime_root_contract

FIXTURE_PATH = Path("tests/fixtures/runtime_root_cases.json")


def load_fixture_cases() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _fixture_runtime_dir_usable(case: dict[str, Any], path: Path, uid: int) -> bool:
    if uid != case["uid"]:
        return False
    xdg = case.get("xdg_runtime_dir")
    if xdg and path == Path(xdg):
        return bool(case.get("xdg_usable", True))
    run_user = Path(f"/run/user/{case['uid']}")
    if path == run_user:
        return bool(case["run_user_usable"])
    return False


def _getenv_for_case(case: dict[str, Any], key: str) -> str | None:
    if key == "ALPHALOOP_RUNTIME_ROOT":
        return case["env"].get("ALPHALOOP_RUNTIME_ROOT")
    if key == "XDG_RUNTIME_DIR":
        return case.get("xdg_runtime_dir") or case["env"].get("XDG_RUNTIME_DIR")
    return case["env"].get(key)


@pytest.mark.parametrize("case", load_fixture_cases(), ids=lambda c: c["id"])
def test_python_contract_matches_shared_fixture(case: dict[str, Any], tmp_path: Path) -> None:
    temp_dir = tmp_path / "temp-root"
    temp_dir.mkdir()
    # Fixture uses "/tmp" for temp_fallback; map to writable tmp_path for mkdir side effects.
    temp_for_case = Path(case["temp_dir"]) if case["id"] != "temp_fallback" else temp_dir
    root = resolve_runtime_root_contract(
        uid=case["uid"],
        temp_dir=temp_for_case,
        getenv=lambda key, _case=case: _getenv_for_case(_case, key),
        runtime_dir_usable=lambda path, uid, _case=case: _fixture_runtime_dir_usable(_case, path, uid),
    )
    expected = Path(case["expected_root"])
    if case["id"] == "temp_fallback":
        expected = temp_dir / f"runtime-{case['uid']}" / "alphaloop"
    assert root == expected


def test_production_python_delegates_to_platformdirs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHALOOP_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    from platformdirs import user_runtime_path

    assert resolve_runtime_root() == Path(user_runtime_path("alphaloop", ensure_exists=False))


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux contract parity")
def test_contract_matches_platformdirs_with_mocked_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contract resolver matches platformdirs when probes follow the same usable-dir rules."""
    monkeypatch.delenv("ALPHALOOP_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    uid = os.getuid()
    from platformdirs import user_runtime_path

    expected = Path(user_runtime_path("alphaloop", ensure_exists=False))
    from engine.research.runtime_contract import _production_runtime_dir_usable

    actual = resolve_runtime_root_contract(
        uid=uid,
        temp_dir=Path(os.environ.get("TMPDIR", "/tmp")),
        getenv=os.environ.get,
        runtime_dir_usable=_production_runtime_dir_usable,
    )
    assert actual == expected


def test_rust_shared_fixture_table() -> None:
    tauri_dir = Path("apps/desktop/src-tauri")
    proc = subprocess.run(
        ["cargo", "test", "-q", "shared_fixture_table_runtime_root", "--", "--exact"],
        cwd=tauri_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_runtime_root_contract_doc_references_fixture() -> None:
    doc = Path("docs/requirements/paths-contract.md").read_text(encoding="utf-8")
    assert "ALPHALOOP_RUNTIME_ROOT" in doc
    assert "runtime-<uid>" in doc
    assert "runtime_root_cases.json" in doc
