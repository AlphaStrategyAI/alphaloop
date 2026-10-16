from pathlib import Path


def test_ci_runs_cargo_check_for_src_tauri() -> None:
    workflow = Path(".github/workflows/desktop-tauri-rust.yml").read_text(encoding="utf-8")
    assert "cargo check" in workflow
    assert "apps/desktop/src-tauri" in workflow or "working-directory: apps/desktop/src-tauri" in workflow
