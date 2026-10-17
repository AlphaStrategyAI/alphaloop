"""Methods library view must not expose raw JSON bodies."""

import json
import re
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore

LEAK = re.compile(
    r"(\{|\}|\":|\\\\u|[a-z]+_[a-z]+|scorecard-v1|walk-v1|cost-v1|pit-v1|"
    r"Point-in-Time|Lookahead bias|Every evidence)"
)


def test_methods_view_all_six_presets_are_structured_chinese(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "methods.db")
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    view = service.view_for("#/methods")
    methods = view["methods"]
    assert len(methods) >= 6
    for item in methods:
        display = item["definitionDisplay"]
        assert "{" not in display
        assert "}" not in display
        assert ":" not in display or "：" in display
        assert not LEAK.search(display)
        assert not LEAK.search(item["description"])
        body = json.loads(store.latest_method_definition(item["id"]).body)
        assert "revision" in body
