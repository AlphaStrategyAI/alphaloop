"""SQLite reload must restore Path fields on Attempt (reverify / strategy_pack)."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from engine.main import ResearchCommandService
from engine.research.models import (
    AssetClass,
    Attempt,
    ChangeClass,
    Market,
    ResearchStatus,
    ReviewReport,
    Universe,
    Version,
    new_research,
)
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.strategy import MeanReversionStrategy, StrategySpec
from engine.verifiers import VerificationReport, VerifierResult
from tests.test_export_pack import accepted_report

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _research_with_snapshot_csv(tmp_path: Path) -> tuple[SQLiteStore, str]:
    store = SQLiteStore(tmp_path / "paths.db")
    snap = tmp_path / "snap.csv"
    pd.DataFrame({"AAA": [1.0, 2.0]}, index=pd.to_datetime(["2020-01-01", "2020-01-02"])).to_csv(
        snap,
        index_label="date",
    )
    spec = StrategySpec(
        id="s-1",
        thesis_locked="t",
        universe=Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA",)),
        frequency="1d",
        side="long_only",
        method_set=(),
        model_family="mean_reversion",
        lookback_days=2,
        entry_z=0.5,
    )
    gate = VerifierResult("scorecard.market", "scorecard-v1", True, {}, "ok")
    attempt = Attempt(
        attempt_id="a-1",
        number=1,
        change_class=ChangeClass.PARAM,
        spec=spec,
        simulation=accepted_report(),
        verification=VerificationReport((gate,) * 5),
        review=ReviewReport(True, ()),
        data_snapshot_path=snap,
        evidence_paths=(tmp_path / "evidence.json",),
    )
    (tmp_path / "evidence.json").write_text('{"material_id": "m-1"}', encoding="utf-8")
    research = replace(
        new_research("r-path", NOW),
        status=ResearchStatus.COMPLETED,
        versions=(
            Version("v1", 1, new_research("r-path", NOW).brief, (), NOW, "confirm_run"),
        ),
        current_version_number=1,
    )
    from engine.research.models import ImplementationDelta, LogicStatement, RoundV2, TrialCounters

    round_ = RoundV2(
        "r1",
        1,
        attempt,
        NOW,
        LogicStatement("logic", False, baseline_version=1),
        ImplementationDelta(),
        TrialCounters(1, 1, 1),
    )
    version = Version("v1", 1, research.brief, (round_,), NOW, "confirm_run")
    research = replace(research, versions=(version,))
    store.create(research)
    return store, research.research_id


def test_reload_restores_path_fields(tmp_path: Path) -> None:
    store, research_id = _research_with_snapshot_csv(tmp_path)
    loaded = store.load(research_id)
    attempt = loaded.versions[0].rounds[0].accepted_attempt
    assert isinstance(attempt.data_snapshot_path, Path)
    assert isinstance(attempt.evidence_paths[0], Path)


def test_path_fields_support_read_text_after_reload(tmp_path: Path) -> None:
    store, research_id = _research_with_snapshot_csv(tmp_path)
    loaded = store.load(research_id)
    attempt = loaded.versions[0].rounds[0].accepted_attempt
    assert "date" in attempt.data_snapshot_path.read_text(encoding="utf-8")
    assert "material_id" in attempt.evidence_paths[0].read_text(encoding="utf-8")
