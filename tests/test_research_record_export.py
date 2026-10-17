import json
import zipfile
from pathlib import Path

import pytest

from engine.export import build_research_record_pack
from tests.test_cumulative_trials import FailTwiceThenPassBuilder
from engine.research.clock import TimeBudget
from engine.research.loop import ResearchLoop
from engine.research.store import SQLiteStore
from tests.test_loop_runtime import NOW, PassReviewer, running_research


def test_research_record_includes_rounds_json_with_cumulative_m(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "5")
    store = SQLiteStore(tmp_path / "rec.db")
    store.create(running_research())
    completed = ResearchLoop(
        store,
        FailTwiceThenPassBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    for _ in range(2):
        completed = ResearchLoop(
            store,
            FailTwiceThenPassBuilder(),
            PassReviewer(),
            TimeBudget(lambda: 10.0),
            lambda: NOW,
        ).run_once("r-loop")

    destination = tmp_path / "record.zip"
    build_research_record_pack(completed, destination)
    with zipfile.ZipFile(destination) as archive:
        rounds = json.loads(archive.read("history/rounds.json"))
        attempts = json.loads(archive.read("history/verification_attempts.json"))
    assert rounds["cumulative_rounds_on_window"] >= 1
    assert rounds["data_window_key"]
    assert rounds["rounds"]
    assert rounds["rounds"][0]["cumulative_round_on_window"] == 1
    assert attempts[0]["data_window_key"] is not None
    assert attempts[0]["cumulative_rounds_on_window"] >= 1
