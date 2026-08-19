from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "src" / "alphaloop"


def _iter_py(package: str):
    folder = ROOT / package
    if not folder.exists():
        return
    for path in folder.rglob("*.py"):
        yield path, path.read_text(encoding="utf-8")


def test_runtime_does_not_import_live():
    for path, text in _iter_py("runtime"):
        assert "alphaloop.live" not in text, path
        assert "from ..live" not in text, path
        assert "from .live" not in text, path


def test_only_worker_may_import_loop():
    for path, text in _iter_py("runtime"):
        if path.name == "worker.py":
            continue
        assert "alphaloop.loop" not in text, path
        assert "from ..loop" not in text, path


def test_loop_does_not_import_runtime_or_bundle():
    for path, text in _iter_py("loop"):
        assert "alphaloop.runtime" not in text, path
        assert "alphaloop.contracts.bundle" not in text, path
