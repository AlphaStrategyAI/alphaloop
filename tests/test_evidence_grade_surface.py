"""PR6: the desktop view and the direct grade function report the same evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.evidence_window import authorize_evidence_split, evidence_grade_view
from engine.research.models import (
    AssetClass,
    ConfirmKind,
    ConfirmRequest,
    Market,
    ResearchStatus,
    new_research,
)
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.symbol_pool import SymbolPool
from tests.test_dialogue_actions import NOW
from tests.test_export_pack import completed_research


def _service(tmp_path: Path) -> ResearchCommandService:
    return ResearchCommandService(
        SQLiteStore(tmp_path / "research.db"),
        EnginePaths.for_colocated_root(tmp_path),
    )


def test_draft_and_awaiting_views_match_the_direct_grade(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.handle({"type": "create_draft"})
    research_id = created["research_id"]
    research = service.store.load(research_id)
    view = service.view_for(f"#/research/{research_id}")
    assert view["evidenceGrade"] == evidence_grade_view(research)
    assert view["evidenceGrade"]["grade"] == "legacy"
    assert view["evidenceGrade"]["reason"] == ""

    card = ConfirmRequest(
        request_id="card-grade",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="改前 改后",
        reason="留出",
        effect="拒绝",
        created_at=NOW,
    )
    waiting = replace(
        new_research("r-wait", NOW),
        status=ResearchStatus.AWAITING_CONFIRM,
        pending_confirm=card,
    )
    service.store.create(waiting)
    waiting_view = service.view_for("#/research/r-wait")
    assert waiting_view["kind"] == "awaiting_confirm"
    assert waiting_view["evidenceGrade"] == evidence_grade_view(service.store.load("r-wait"))


def test_late_constituent_list_stays_exploratory_on_the_api(tmp_path: Path, monkeypatch) -> None:
    late = SymbolPool(
        version_id="late",
        display_name="late",
        generated_date="2024-06-01",
        market=Market.US,
        asset_class=AssetClass.EQUITY,
        underlying_asset_class=AssetClass.EQUITY,
        symbols=("AAPL",),
        actual_available_at="2024-06-01",
        source_fingerprint="late-fingerprint",
    )
    as_of = date(2024, 1, 1)
    research = completed_research()
    research = replace(
        research,
        symbol_list_version="late",
        evidence_policy=authorize_evidence_split(
            research,
            explore_end=as_of,
            holdout_start=date(2024, 1, 2),
            holdout_end=date(2024, 6, 1),
            mode="final",
        ).evidence_policy,
    )
    monkeypatch.setattr(
        "engine.research.evidence_window.pool_by_version",
        lambda version_id: late if version_id == "late" else None,
    )
    service = _service(tmp_path)
    service.store.create(research)
    view = service.view_for("#/research/r-export")
    direct = evidence_grade_view(service.store.load("r-export"))
    assert view["kind"] == "completed"
    assert view["evidenceGrade"] == direct
    assert direct["grade"] == "exploratory"
    assert "晚于探索截止日" in direct["reason"]
    assert direct["grade"] != "final"
