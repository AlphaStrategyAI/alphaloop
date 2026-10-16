from pathlib import Path


def test_on_exit_block_returns_closure_not_unit() -> None:
    source = Path("apps/desktop/src-tauri/src/lib.rs").read_text(encoding="utf-8")
    assert "let on_exit = {" in source
    # Block must end with closure expression, not `};` after a discarded closure call.
    assert "move || schedule_sidecar_restart" in source
    bad = "move || schedule_sidecar_restart(app_handle, supervisor, connection, runtime, \"process exited\");"
    assert bad not in source
