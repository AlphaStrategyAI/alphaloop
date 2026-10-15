from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from engine.main import ResearchCommandService
from engine.research.methods import create_method
from engine.research.models import MethodSource
from engine.research.runtime import RuntimePaths
from engine.research.store import SQLiteStore

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def test_methods_view_selects_percent_encoded_non_ascii_id(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "m.db")
    method_id = "user.e2e测试"
    create_method(store, method_id, "E2E", "desc", "body", MethodSource.DEPOSITED, NOW)
    service = ResearchCommandService(
        store,
        RuntimePaths(tmp_path, tmp_path / "lock", tmp_path / "owner.json"),
    )
    encoded = quote(method_id, safe="")
    view = service.view_for(f"#/methods/{encoded}")
    assert view["selected"] == method_id
    assert any(item["id"] == method_id for item in view["methods"])
