"""Single-slot unlock on confirm card returns to draft then back to confirm."""

from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from tests.test_draft_confirm_run_e2e import DIALOGUE_SEQUENCE, _service


def test_unlock_one_slot_then_reconfirm(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = service.handle({"type": "create_draft"})["research_id"]
    for message in DIALOGUE_SEQUENCE:
        service.handle(
            {"type": "send_dialogue", "research_id": research_id, "message": message}
        )
    assert service.view_for(f"#/research/{research_id}")["kind"] == "confirm_run"

    service.handle(
        {"type": "unlock_brief", "research_id": research_id, "slot": "max_effective_hours"}
    )
    draft = service.view_for(f"#/research/{research_id}")
    assert draft["kind"] == "draft"
    assert draft["settings"]["max_effective_hours"] == ""

    service.handle(
        {
            "type": "send_dialogue",
            "research_id": research_id,
            "message": "最长研究时间改成 10 小时",
        }
    )
    confirm = service.view_for(f"#/research/{research_id}")
    assert confirm["kind"] == "confirm_run"
    assert "10" in confirm["settings"]["max_effective_hours"]
