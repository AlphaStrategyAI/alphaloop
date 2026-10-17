from datetime import UTC, datetime
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.verifiers import VerificationReport
from tests.test_export_pack import completed_research


def test_store_roundtrip_preserves_verification_report(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "store.db")
    research = completed_research()
    store.create(research)
    loaded = store.load(research.research_id)
    verification = loaded.versions[0].rounds[0].accepted_attempt.verification
    assert isinstance(verification, VerificationReport)
    paths = EnginePaths.for_colocated_root(tmp_path)
    view = ResearchCommandService(store, paths).view_for(f"#/research/{research.research_id}")
    assert view["kind"] == "completed"
