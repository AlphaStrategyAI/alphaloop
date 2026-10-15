import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "desktop-api.schema.json"
COMMANDS_RS = ROOT / "apps" / "desktop" / "src-tauri" / "src" / "commands.rs"
MAIN_PY = ROOT / "engine" / "main.py"


def _schema_request_types(schema: dict) -> set[str]:
    types: set[str] = set()
    for branch in schema["oneOf"]:
        props = branch.get("properties", {})
        type_prop = props.get("type")
        if not type_prop:
            continue
        if "const" in type_prop:
            types.add(type_prop["const"])
        if "enum" in type_prop:
            types.update(type_prop["enum"])
    return types


def _handle_kinds(main_source: str) -> set[str]:
    kinds = set(re.findall(r'\bkind == "([a-z_]+)"', main_source))
    kinds.update(re.findall(r'\belif kind == "([a-z_]+)"', main_source))
    return kinds


def _commands_rs_types(commands_source: str) -> set[str]:
    return set(re.findall(r'"type":\s*"([a-z_]+)"', commands_source))


def test_desktop_schema_covers_engine_and_tauri_command_types() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_types = _schema_request_types(schema)
    handle_types = _handle_kinds(MAIN_PY.read_text(encoding="utf-8"))
    rust_types = _commands_rs_types(COMMANDS_RS.read_text(encoding="utf-8"))

    missing_from_schema = (handle_types | rust_types) - schema_types
    assert not missing_from_schema, f"schema missing types: {sorted(missing_from_schema)}"

    extra_in_schema = schema_types - handle_types
    assert not extra_in_schema, f"schema has unknown types: {sorted(extra_in_schema)}"
