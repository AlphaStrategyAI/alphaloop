from pathlib import Path


def test_build_and_smoke_scripts_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    build = root / "scripts" / "build_sidecar.sh"
    smoke = root / "scripts" / "smoke_sidecar.sh"
    assert build.is_file()
    assert smoke.is_file()
    spec = (root / "packaging" / "alphaloop-engine.spec").read_text(encoding="utf-8")
    assert "collect_data_files(\"akshare\")" in spec
    tauri = (root / "apps" / "desktop" / "src-tauri" / "tauri.conf.json").read_text(
        encoding="utf-8"
    )
    assert '"resources/engine/alphaloop-engine": "engine/alphaloop-engine"' in tauri.replace(
        "\n", ""
    ) or '"resources/engine/alphaloop-engine": "engine/alphaloop-engine"' in tauri
    assert "**/*" not in tauri
