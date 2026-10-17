from pathlib import Path


def test_build_sidecar_script_checks_libpython() -> None:
    script = Path("scripts/build_sidecar.sh").read_text(encoding="utf-8")
    assert "libpython" in script
    assert "ldd" in script
    assert "python${PY_MINOR}-dev" in script or "libpython${PY_MINOR}" in script
    assert '[[ "$(uname -s)" == "Linux" ]]' in script
    assert script.index('[[ "$(uname -s)" == "Linux" ]]') < script.index(
        "libpython${PY_MINOR}.so"
    )
