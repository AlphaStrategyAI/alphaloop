from pathlib import Path


def test_engine_spec_collects_py_mini_racer_binaries() -> None:
    spec = Path("packaging/alphaloop-engine.spec").read_text(encoding="utf-8")
    assert "collect_py_mini_racer_binaries" in spec
    assert "packaging.pyinstaller_binaries" in spec


def test_collect_py_mini_racer_binaries_returns_pairs_when_installed() -> None:
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "alphaloop_pyinstaller_binaries",
        root / "packaging" / "pyinstaller_binaries.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    pairs = module.collect_py_mini_racer_binaries()
    # CI/dev may or may not have py_mini_racer native libs; shape must be valid.
    for src, dest in pairs:
        assert dest == "."
        assert "libmini_racer" in Path(src).name
