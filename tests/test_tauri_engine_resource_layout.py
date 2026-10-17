import json
import subprocess
import sys
from pathlib import Path


def test_tauri_conf_uses_directory_resource_not_glob() -> None:
    conf = json.loads(
        Path("apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
    )
    resources = conf["bundle"]["resources"]
    assert "resources/engine/alphaloop-engine" in resources
    key = "resources/engine/alphaloop-engine"
    assert resources[key] == "engine/alphaloop-engine"
    assert "**/*" not in json.dumps(resources)


def test_build_script_uses_venv_not_system_pip() -> None:
    build = Path("scripts/build_sidecar.sh").read_text(encoding="utf-8")
    assert ".venv-sidecar" in build
    assert '"$VENV_PY" -m pip' in build
    assert "python3 -m pip install" not in build


def test_verify_layout_script_accepts_valid_tree(tmp_path: Path) -> None:
    root = tmp_path / "alphaloop-engine"
    internal = root / "_internal"
    internal.mkdir(parents=True)
    (root / "alphaloop-engine").write_text("#!/bin/sh\n", encoding="utf-8")
    (internal / "libpython.stub").write_text("x", encoding="utf-8")
    script = Path("scripts/verify_engine_resource_layout.py")
    repo = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, str(script), "--source", str(root)],
        check=True,
        cwd=repo,
    )


def test_verify_layout_script_accepts_windows_exe_tree(tmp_path: Path) -> None:
    root = tmp_path / "alphaloop-engine"
    internal = root / "_internal"
    internal.mkdir(parents=True)
    (root / "alphaloop-engine.exe").write_bytes(b"MZ")
    (internal / "base_library.zip").write_bytes(b"pk")
    script = Path("scripts/verify_engine_resource_layout.py")
    repo = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, str(script), "--source", str(root)],
        check=True,
        cwd=repo,
    )
