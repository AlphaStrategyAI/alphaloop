"""UI language resolution and request-locale passthrough. Research rows stay language-free."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from engine.i18n.locale import (
    get_request_locale,
    language_from_system_locale,
    load_ui_language_cases,
    normalize_request_locale,
    resolve_ui_language,
)
from engine.main import ResearchCommandService
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "desktop-api.schema.json"


def test_system_locale_cases_match_the_shared_fixture() -> None:
    cases = load_ui_language_cases()
    for case in cases["systemTags"]:
        assert language_from_system_locale(case["tag"]) == case["language"], case["id"]
    for case in cases["resolution"]:
        assert (
            resolve_ui_language(case["preference"], case["system"]) == case["resolved"]
        ), case["id"]


def test_request_locale_only_accepts_resolved_languages() -> None:
    assert normalize_request_locale("zh") == "zh"
    assert normalize_request_locale("en") == "en"
    assert normalize_request_locale("zh-CN") is None
    assert normalize_request_locale("system") is None
    assert normalize_request_locale(None) is None


def test_handle_threads_locale_without_writing_it_on_the_research(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    seen: dict[str, str | None] = {}

    original = service._dispatch

    def spy(request: dict) -> dict:
        seen["during"] = get_request_locale()
        return original(request)

    service._dispatch = spy  # type: ignore[method-assign]
    created = service.handle({"type": "create_draft", "locale": "zh"})
    assert seen["during"] == "zh"
    assert service.last_request_locale == "zh"
    assert get_request_locale() is None

    raw = store.connection.execute(
        "SELECT state_json FROM researches WHERE research_id = ?",
        (created["research_id"],),
    ).fetchone()[0]
    payload = json.loads(raw)

    def walk(value: object) -> None:
        if isinstance(value, dict):
            assert "locale" not in value
            assert "uiLanguage" not in value
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)


def test_missing_locale_leaves_request_scope_empty(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    service.handle({"type": "create_draft"})
    assert service.last_request_locale is None


def test_schema_allows_resolved_locale_and_rejects_other_tags() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate({"type": "create_draft", "locale": "en"}, schema)
    jsonschema.validate({"type": "fetch_view", "route": "#/research", "locale": "zh"}, schema)
    jsonschema.validate({"type": "create_draft"}, schema)
    try:
        jsonschema.validate({"type": "create_draft", "locale": "fr"}, schema)
    except jsonschema.ValidationError:
        return
    raise AssertionError("schema accepted a non-resolved locale")
