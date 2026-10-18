"""Shared binary discovery for PyInstaller (importable from alphaloop-engine.spec)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def collect_py_mini_racer_binaries() -> list[tuple[str, str]]:
    """Bundle libmini_racer native libs required by akshare Sina endpoints."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []

    def add(path: Path) -> None:
        key = path.name
        if not path.is_file() or key in seen:
            return
        seen.add(key)
        out.append((str(path.resolve()), "."))

    spec = importlib.util.find_spec("py_mini_racer")
    if spec and spec.submodule_search_locations:
        pkg = Path(next(iter(spec.submodule_search_locations)))
        for name in (
            "libmini_racer.glibc.so",
            "libmini_racer.so",
            "libmini_racer.dylib",
            "libmini_racer.dll",
        ):
            add(pkg / name)

    for prefix in (Path(sys.prefix), Path(sys.base_prefix)):
        site = prefix / "lib"
        if site.is_dir():
            for path in site.rglob("libmini_racer*.so"):
                add(path)
            for path in site.rglob("libmini_racer*.dylib"):
                add(path)

    root = Path(__file__).resolve().parents[1]
    venv = root / ".venv-sidecar"
    if venv.is_dir():
        for path in venv.rglob("libmini_racer*"):
            if path.is_file():
                add(path)

    return out
