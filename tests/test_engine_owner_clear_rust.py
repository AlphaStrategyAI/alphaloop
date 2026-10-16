from pathlib import Path


def test_restart_sidecar_clears_owner_file_before_start() -> None:
    commands = Path("apps/desktop/src-tauri/src/commands.rs").read_text(encoding="utf-8")
    assert "pub fn restart_engine_sidecar" in commands
    restart_block = commands.split("pub fn restart_engine_sidecar", 1)[1].split("}", 1)[0]
    assert "clear_owner_file" in restart_block
    assert "connection.clear()" in restart_block


def test_schedule_sidecar_restart_clears_owner_when_cap_exceeded() -> None:
    restart = Path("apps/desktop/src-tauri/src/sidecar_restart.rs").read_text(encoding="utf-8")
    assert "schedule_sidecar_recovery" in restart
    assert "clear_owner_file_logged" in restart
    assert "connection.clear()" in restart


def test_engine_paths_module_has_owner_clear_test() -> None:
    src = Path("apps/desktop/src-tauri/src/engine_paths.rs").read_text(encoding="utf-8")
    assert "fn clear_owner_file_at_removes_existing_file" in src
    assert "resolve_runtime_root" in src
    assert "clear_owner_file_logged" in src


def test_sidecar_restart_module_has_recovery_tests() -> None:
    src = Path("apps/desktop/src-tauri/src/sidecar_restart.rs").read_text(encoding="utf-8")
    assert "schedule_sidecar_recovery" in src
    assert "handshake_failure_retries_with_backoff_until_stopped" in src
