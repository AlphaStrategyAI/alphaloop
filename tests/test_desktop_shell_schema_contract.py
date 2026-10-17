import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL_SCHEMA = ROOT / "contracts" / "desktop-shell.schema.json"
COMMANDS_RS = ROOT / "apps" / "desktop" / "src-tauri" / "src" / "commands.rs"


def test_shell_sidecar_commands_registered() -> None:
    schema = json.loads(SHELL_SCHEMA.read_text(encoding="utf-8"))
    props = set(schema.get("properties", {}))
    rust = COMMANDS_RS.read_text(encoding="utf-8")
    for command in ("engine_sidecar_state", "restart_engine_sidecar"):
        assert command in props
        assert re.search(rf"pub fn {command}\b", rust) or re.search(
            rf"pub async fn {command}\b", rust
        )
