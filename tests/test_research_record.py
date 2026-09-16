import json
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from engine.export import (
    build_research_record_pack,
    build_strategy_pack,
    importer_accepts,
    mark_exports_overturned,
    strategy_pack_eligibility,
)
from engine.research.models import (
    ExportKind,
    ExportRecord,
    ResearchStatus,
    Reverification,
)
from tests.test_export_pack import completed_research, reference_strategy
from engine.strategy import MarketPanel
import pandas as pd

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def test_research_record_identity_is_rejectable_without_reading_copy(tmp_path: Path) -> None:
    ended = replace(completed_research(), status=ResearchStatus.ENDED, export_eligible=False)
    path = build_research_record_pack(ended, tmp_path / "record.zip")
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["kind"] == "research_record"
    assert manifest["live_handoff_eligible"] is False
    assert importer_accepts(manifest) is False


def test_strategy_pack_identity_is_the_only_live_handoff_kind(tmp_path: Path) -> None:
    research = completed_research()
    prices = pd.DataFrame(
        {"AAA": [10.0, 11.0, 9.5], "BBB": [8.0, 7.5, 8.5]},
        index=pd.DatetimeIndex(["2020-01-02", "2020-01-03", "2020-01-06"], name="date"),
    )
    panel = MarketPanel(prices, prices.mean(axis=1).rename("SPX"))
    path = build_strategy_pack(research, reference_strategy(), panel, tmp_path / "pack.zip")
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        provenance = json.loads(archive.read("data/provenance.json"))
        methods = json.loads(archive.read("methods/definitions.json"))
    assert manifest["kind"] == "strategy_pack"
    assert manifest["live_handoff_eligible"] is True
    assert importer_accepts(manifest) is True
    assert "coverage_floor" in provenance
    assert "shrinks" in provenance
    assert methods


def test_reverify_fail_marks_prior_exports_overturned_without_rewriting_files(tmp_path: Path) -> None:
    exported = replace(
        completed_research(),
        exports=(
            ExportRecord(
                "e-1",
                ExportKind.STRATEGY_PACK,
                str(tmp_path / "old.zip"),
                1,
                NOW,
                (),
                False,
            ),
        ),
    )
    (tmp_path / "old.zip").write_bytes(b"frozen")
    failed = replace(
        exported,
        reverifications=(
            Reverification("r-export-v1-r1", "overfit.walk", None, False, NOW),
        ),
    )
    updated = mark_exports_overturned(failed)
    eligibility = strategy_pack_eligibility(updated)
    assert eligibility.eligible is False
    assert updated.exports[0].overturned is True
    assert (tmp_path / "old.zip").read_bytes() == b"frozen"
