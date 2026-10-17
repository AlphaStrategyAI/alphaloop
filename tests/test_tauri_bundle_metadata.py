import json
from pathlib import Path


def test_tauri_bundle_has_icons_and_descriptions() -> None:
    conf = json.loads(Path("apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    bundle = conf.get("bundle", {})
    icons = bundle.get("icon")
    assert icons, "bundle.icon must list icon files"
    icon_dir = Path("apps/desktop/src-tauri")
    for entry in icons:
        assert (icon_dir / entry).is_file(), f"missing icon {entry}"
    assert bundle.get("category") == "Finance"
    assert bundle.get("shortDescription")
    assert bundle.get("longDescription")


def test_tauri_identifier_matches_data_dir() -> None:
    conf = json.loads(Path("apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    assert conf.get("identifier") == "ai.alphastrategy.alphaloop"
