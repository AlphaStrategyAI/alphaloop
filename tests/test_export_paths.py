from datetime import UTC, datetime
from pathlib import Path

from engine.export_paths import export_zip_filename
from engine.main import ResearchCommandService
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from tests.test_state_machine import locked_brief
from engine.research.models import new_research, ResearchStatus
from dataclasses import replace

NOW = datetime(2026, 10, 17, 8, 0, tzinfo=UTC)


def test_export_zip_filename_is_readable() -> None:
    research = replace(
        new_research("abcd1234-5678-90ab-cdef", NOW),
        brief=locked_brief(),
    )
    name = export_zip_filename(research, "research_record", now=NOW)
    assert "abcd1234" in name
    assert "研究记录" in name
    assert name.endswith(".zip")
    assert research.research_id not in name


def test_export_artifact_uses_readable_name(tmp_path: Path) -> None:
    from tests.test_export_pack import completed_research

    store = SQLiteStore(tmp_path / "exp.db")
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    research = replace(completed_research(), research_id="r-exp")
    store.create(research)
    result = service.handle(
        {
            "type": "export_artifact",
            "research_id": "r-exp",
            "kind": "research_record",
        }
    )
    assert "path" in result
    assert "研究记录" in result["path"]
