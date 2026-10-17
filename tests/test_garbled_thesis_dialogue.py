from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore


def test_garbled_thesis_rejected_with_example(tmp_path: Path) -> None:
    service = ResearchCommandService(
        SQLiteStore(tmp_path / "g.db"),
        EnginePaths.for_colocated_root(tmp_path),
    )
    rid = service.handle({"type": "create_draft"})["research_id"]
    service.handle({"type": "send_dialogue", "research_id": rid, "message": "随便乱打一串字"})
    view = service.view_for(f"#/research/{rid}")
    assert view["kind"] == "draft"
    assistant = [t["text"] for t in view["dialogue"] if t["role"] == "assistant"]
    assert assistant
    assert "没能理解" in assistant[-1]
    assert "均值回归" in assistant[-1] or "赚钱" in assistant[-1]
    assert service.store.load(rid).brief.thesis.value is None
