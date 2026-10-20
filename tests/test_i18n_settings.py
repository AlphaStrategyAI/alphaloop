"""UI language preference file: data directory, legacy-neutral reads, keys preserved."""

from __future__ import annotations

import json
from pathlib import Path

from engine.i18n.settings_store import (
    read_ui_language_preference,
    write_ui_language_preference,
)
from engine.research.data_paths import DataPaths


def test_missing_file_follows_system(tmp_path: Path) -> None:
    assert read_ui_language_preference(tmp_path / "settings.json") == "system"


def test_preference_round_trip_preserves_unrelated_keys(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"dataSources": {"kept": True}, "uiLanguage": "en"}), encoding="utf-8")
    assert read_ui_language_preference(path) == "en"
    write_ui_language_preference("zh", path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["uiLanguage"] == "zh"
    assert loaded["dataSources"] == {"kept": True}
    assert read_ui_language_preference(path) == "zh"


def test_unknown_and_corrupt_preferences_are_legacy_neutral(tmp_path: Path) -> None:
    unknown = tmp_path / "unknown.json"
    unknown.write_text(json.dumps({"uiLanguage": "fr", "other": 1}), encoding="utf-8")
    assert read_ui_language_preference(unknown) == "system"

    missing_key = tmp_path / "missing.json"
    missing_key.write_text(json.dumps({"other": 1}), encoding="utf-8")
    assert read_ui_language_preference(missing_key) == "system"

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    assert read_ui_language_preference(corrupt) == "system"
    write_ui_language_preference("en", corrupt)
    assert json.loads(corrupt.read_text(encoding="utf-8"))["uiLanguage"] == "en"


def test_data_paths_point_at_the_settings_file(tmp_path: Path) -> None:
    paths = DataPaths(tmp_path)
    assert paths.settings_file == tmp_path / "settings.json"


def test_write_rejects_unknown_preference(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    try:
        write_ui_language_preference("fr", path)
    except ValueError:
        assert not path.exists()
        return
    raise AssertionError("unknown preference was stored")
