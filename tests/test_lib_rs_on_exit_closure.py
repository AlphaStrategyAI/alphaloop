from pathlib import Path


def test_on_exit_block_returns_closure_not_unit() -> None:
    source = Path("apps/desktop/src-tauri/src/lib.rs").read_text(encoding="utf-8")
    assert "let on_exit = {" in source
    start = source.index("let on_exit = {")
    block = source[start : source.index("match handshake.status", start)]
    # The block must produce a closure. A discarded call would end the block
    # with a statement, and the sidecar would not be restarted.
    assert "move ||" in block
    assert "schedule_sidecar_restart" in block
    assert not block.rstrip().endswith('");')
