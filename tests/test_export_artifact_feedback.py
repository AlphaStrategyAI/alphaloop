import json
from pathlib import Path

import jsonschema

from engine.main import ResearchCommandService
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from tests.test_export_pack import completed_research


def test_export_artifact_handle_returns_path(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "export.db")
    paths = EnginePaths.for_colocated_root(tmp_path)
    research = completed_research()
    store.create(research)
    service = ResearchCommandService(store, paths)

    payload = service.handle(
        {
            "type": "export_artifact",
            "research_id": research.research_id,
            "kind": "research_record",
        }
    )
    schema = json.loads(
        Path("contracts/desktop-export-response.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(payload, schema)
    assert Path(payload["path"]).is_file()
