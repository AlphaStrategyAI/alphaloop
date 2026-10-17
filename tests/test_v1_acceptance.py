import json
import os
import zipfile
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import jsonschema
import pandas as pd
import pytest

from engine.export import build_strategy_pack, strategy_pack_eligibility
from engine.main import ResearchCommandService, build_loop
from engine.metrics import SimulationReport
from engine.research.models import (
    AssetClass,
    Attempt,
    ChangeClass,
    ConfirmKind,
    ConfirmRequest,
    ImplementationDelta,
    LogicStatement,
    Market,
    MethodRef,
    ResearchEvent,
    ResearchStatus,
    ReviewReport,
    Reverification,
    RoundV2,
    Slot,
    TrialCounters,
    Universe,
    Version,
    new_research,
)
from engine.research.runtime import EnginePaths
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.strategy import MarketPanel, MeanReversionStrategy, StrategySpec
from engine.verifiers import PitVerifierResult, VerificationReport, VerifierResult, run_verifiers
from tests.test_export_pack import accepted_report, completed_research, reference_strategy

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def _round_v2(attempt: Attempt) -> RoundV2:
    return RoundV2(
        round_id="v1-r1",
        number=1,
        accepted_attempt=attempt,
        completed_at=NOW,
        logic_statement=LogicStatement(
            "低波动均值回归 thesis 片段",
            False,
            baseline_version=1,
        ),
        implementation_delta=ImplementationDelta(
            param_changes=(("lookback_days", "20", "25"),),
        ),
        trial_counters=TrialCounters(3, 1, 2),
    )


def _paths(tmp_path: Path) -> EnginePaths:
    return EnginePaths.for_colocated_root(tmp_path)


def _service(tmp_path: Path) -> ResearchCommandService:
    store = SQLiteStore(tmp_path / "store.db")
    return ResearchCommandService(store, _paths(tmp_path))


def test_running_view_round_fields_from_store(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research = new_research("r-view", NOW)
    gate = VerifierResult("scorecard.market", "scorecard-v1", True, {}, "ok")
    pit = PitVerifierResult(
        verifier_id="pit.consistency",
        revision="pit-v1",
        passed=False,
        values={"violations_count": 1.0},
        rule="test",
        evidence_timestamps=(),
        backtest_cutoff="2026-01-01",
        violations=("missing",),
    )
    spec = reference_strategy().spec
    attempt = Attempt(
        attempt_id="a-1",
        number=2,
        change_class=ChangeClass.PARAM,
        spec=spec,
        simulation=accepted_report(),
        verification=VerificationReport((gate, gate, pit)),
        review=ReviewReport(passed=True, findings=()),
    )
    version = Version(
        "v-1",
        1,
        research.brief,
        (_round_v2(attempt),),
        NOW,
        "confirm_run",
    )
    running = replace(
        research,
        status=ResearchStatus.RUNNING,
        versions=(version,),
        current_version_number=1,
        brief=replace(
            research.brief,
            thesis=Slot("低波动均值回归 thesis", True),
            universe=Slot(
                Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("SPY",)),
                True,
            ),
        ),
    )
    service.store.load = lambda _rid: running  # type: ignore[method-assign]
    view = service.view_for(f"#/research/{running.research_id}")
    round_payload = view["rounds"][0]
    assert "低波动均值回归" in round_payload["logicStatement"]["statement"]
    assert round_payload["trialCounters"]["candidatesEvaluated"] == 3
    assert round_payload["verificationPassed"] is True
    assert round_payload["pitPassed"] is False


def test_completed_view_no_placeholder_copy(tmp_path: Path) -> None:
    service = _service(tmp_path)
    completed = replace(completed_research(), status=ResearchStatus.COMPLETED)
    service.store.load = lambda _rid: completed  # type: ignore[method-assign]
    view = service.view_for(f"#/research/{completed.research_id}")
    assert view["subtitle"] != "美股 · 股票 · 经过市场基准和全部额外验证"
    assert view["title"]


def test_anomaly_baseline_not_hardcoded(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research = completed_research()
    anomaly = service._compute_anomaly(research)
    assert anomaly is None or anomaly.get("baseline", {}).get("sharpe") != 0.5


def test_build_loop_defaults_to_deterministic_reviewer(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "loop.db")
    loop = build_loop(store, _paths(tmp_path))
    from engine.review.deterministic import DeterministicReviewer

    assert isinstance(loop.reviewer, DeterministicReviewer)


def test_strategy_pack_manifest_validates_against_contract_schema(tmp_path: Path) -> None:
    research = completed_research()
    prices = pd.DataFrame(
        {"AAA": [10.0, 11.0, 9.5], "BBB": [8.0, 7.5, 8.5]},
        index=pd.DatetimeIndex(["2020-01-02", "2020-01-03", "2020-01-06"], name="date"),
    )
    panel = MarketPanel(prices, prices.mean(axis=1).rename("SPX"))
    archive = build_strategy_pack(research, reference_strategy(), panel, tmp_path / "pack.zip")
    manifest = json.loads(zipfile.ZipFile(archive).read("manifest.json"))
    schema = json.loads(Path("contracts/strategy-pack.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, schema)
    assert manifest["live_handoff_eligible"] is True
    assert zipfile.ZipFile(archive).read("history/rounds.json")


def test_export_strategy_pack_only_when_eligible(tmp_path: Path) -> None:
    research = completed_research()
    attempt = research.versions[0].rounds[0].accepted_attempt
    updated_results = tuple(
        replace(item, passed=False)
        if item.verifier_id == "pit.consistency"
        else item
        for item in attempt.verification.results
    )
    pit_fail = replace(
        research,
        versions=(
            replace(
                research.versions[0],
                rounds=(
                    replace(
                        research.versions[0].rounds[0],
                        accepted_attempt=replace(
                            attempt,
                            verification=VerificationReport(updated_results),
                        ),
                    ),
                ),
            ),
        ),
    )
    eligibility = strategy_pack_eligibility(pit_fail)
    assert "pit_executed_and_passed" in eligibility.failed_checks
    assert "all_current_methods_passed" not in eligibility.failed_checks


def test_reverify_does_not_double_count_pit(tmp_path: Path) -> None:
    research = completed_research()
    attempt = research.versions[0].rounds[0].accepted_attempt
    updated_results = tuple(
        replace(item, passed=False)
        if item.verifier_id == "pit.consistency"
        else item
        for item in attempt.verification.results
    )
    research = replace(
        research,
        versions=(
            replace(
                research.versions[0],
                rounds=(
                    replace(
                        research.versions[0].rounds[0],
                        accepted_attempt=replace(
                            attempt,
                            verification=VerificationReport(updated_results),
                        ),
                    ),
                ),
            ),
        ),
    )
    rerun = run_verifiers(
        attempt.simulation,
        attempt.spec,
        missing_as_of_material_ids=("md",),
    )
    research = replace(
        research,
        reverifications=(
            Reverification("r-export-v1-r1", "overfit.walk", rerun, True, NOW),
        ),
    )
    failed = strategy_pack_eligibility(research).failed_checks
    assert "pit_executed_and_passed" in failed
    assert "all_reverifies_passed" not in failed


def test_who_pays_recorded_on_confirmed_changes(tmp_path: Path) -> None:
    from engine.research.state_machine import _open_version

    research = new_research("r-who", NOW)
    version = Version("v-1", 1, research.brief, (), NOW, "confirm_run")
    pending = ConfirmRequest(
        request_id="c-1",
        kind=ConfirmKind.ECONOMIC,
        proposed_change="调整参数",
        reason="需要确认",
        effect="开新版本",
        patch=(("lookback_days", 30), ("who_pays_optional", "未作答")),
        created_at=NOW,
    )
    awaiting = replace(
        research,
        status=ResearchStatus.AWAITING_CONFIRM,
        versions=(version,),
        current_version_number=1,
        pending_confirm=pending,
    )
    opened = _open_version(awaiting, NOW, "economic_confirm")
    pairs = opened.versions[-1].confirmed_changes
    assert ("who_pays_optional", "未作答") in pairs
