"""PR5: runtime questions, confirm cards, reverify eligibility, and publish."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from engine.dialogue.actions import MISSING, apply_runtime_dialogue
from engine.export import strategy_pack_eligibility
from engine.main import ResearchCommandService
from engine.research.methods import create_method, execute_method_revision, revise_method
from engine.research.models import (
    Attempt,
    ChangeClass,
    ConfirmKind,
    ConfirmRequest,
    CoverageFloor,
    CoverageSnapshot,
    ExportKind,
    ExportRecord,
    ImplementationDelta,
    LogicStatement,
    MethodRef,
    MethodSource,
    ResearchEvent,
    ResearchStatus,
    Reverification,
    ReviewReport,
    RoundV2,
    Slot,
    TrialCounters,
    Version,
    new_research,
)
from engine.research.reverify_run import reverify_round
from engine.research.runtime import EnginePaths
from engine.research.state_machine import executable_commands, transition
from engine.research.store import SQLiteStore
from engine.verifiers import VerificationReport
from tests.test_export_pack import completed_research
from tests.test_state_machine import locked_brief

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def _service(tmp_path: Path) -> ResearchCommandService:
    store = SQLiteStore(tmp_path / "research.db")
    return ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))


def _save_status(service: ResearchCommandService, research_id: str, status: ResearchStatus, **changes):
    research = service.store.load(research_id)
    updated = replace(research, status=status, updated_at=NOW, **changes)
    service.store.save(updated, research.updated_at)
    return service.store.load(research_id)


def test_questions_are_read_only_in_every_state_and_name_records(tmp_path: Path) -> None:
    service = _service(tmp_path)
    for status in ResearchStatus:
        research_id = f"q-{status.value}"
        service.store.create(new_research(research_id, NOW))
        if status is not ResearchStatus.DRAFT:
            _save_status(service, research_id, status)
        before = service.store.load(research_id)
        service.handle({"type": "send_dialogue", "research_id": research_id, "message": "现在在做什么"})
        loaded = service.store.load(research_id)
        assert loaded.status is status
        assert loaded.brief == before.brief
        reply = loaded.dialogue[-1].text
        assert MISSING in reply
        for command in executable_commands(status):
            assert command in reply


def test_look_is_read_only_and_change_logic_does_not_touch_the_running_brief(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research = replace(
        new_research("r-run", NOW),
        status=ResearchStatus.RUNNING,
        brief=locked_brief(),
    )
    service.store.create(research)
    before = research.brief
    service.handle({"type": "send_dialogue", "research_id": "r-run", "message": "先看看"})
    looked = service.store.load("r-run")
    assert looked.status is ResearchStatus.RUNNING
    assert looked.brief == before

    service.handle({"type": "send_dialogue", "research_id": "r-run", "message": "改逻辑：只比较同行业"})
    proposed = service.store.load("r-run")
    assert proposed.status is ResearchStatus.AWAITING_CONFIRM
    assert proposed.brief == before
    card = proposed.pending_confirm
    assert card is not None
    assert card.request_id
    assert "改前" in card.proposed_change and "改后" in card.proposed_change
    assert "拒绝" in card.effect
    view = service.view_for("#/research/r-run")
    assert view["requestId"] == card.request_id
    assert "whoPaysOptional" in view
    assert view["whyChange"] == [] or view["whyChange"][0]["recordId"]

    with pytest.raises(ValueError, match="stale or cross-research"):
        service.handle(
            {
                "type": "resolve_confirm",
                "research_id": "r-run",
                "decision": "reject_keep_logic",
                "request_id": "someone-elses-card",
            }
        )
    assert service.store.load("r-run").brief == before

    service.handle(
        {
            "type": "resolve_confirm",
            "research_id": "r-run",
            "decision": "reject_keep_logic",
            "request_id": card.request_id,
        }
    )
    rejected = service.store.load("r-run")
    assert rejected.status is ResearchStatus.RUNNING
    assert rejected.brief == before
    assert rejected.pending_confirm is None


def test_stale_card_and_replay_bind_the_original_request(tmp_path: Path) -> None:
    service = _service(tmp_path)
    first = ConfirmRequest(
        request_id="card-a",
        kind=ConfirmKind.COVERAGE,
        proposed_change="改前：底线 改后：更低",
        reason="覆盖",
        effect="开新版或拒绝",
        created_at=NOW,
    )
    research = replace(
        new_research("r-card", NOW),
        status=ResearchStatus.AWAITING_CONFIRM,
        pending_confirm=first,
        versions=(),
    )
    service.store.create(research)
    service.handle(
        {
            "type": "resolve_confirm",
            "research_id": "r-card",
            "decision": "reject_keep_logic",
            "request_id": "card-a",
            "command_id": "cmd-replay",
            "expected_revision": 0,
        }
    )
    again = service.handle(
        {
            "type": "resolve_confirm",
            "research_id": "r-card",
            "decision": "reject_keep_logic",
            "request_id": "card-a",
            "command_id": "cmd-replay",
            "expected_revision": 0,
        }
    )
    assert again["status"] == "running"
    assert service.store.load("r-card").status is ResearchStatus.RUNNING

    other = ConfirmRequest(
        request_id="card-b",
        kind=ConfirmKind.COVERAGE,
        proposed_change="另一张卡",
        reason="覆盖",
        effect="开新版",
        created_at=NOW,
    )
    current = service.store.load("r-card")
    service.store.save(
        replace(current, status=ResearchStatus.AWAITING_CONFIRM, pending_confirm=other, updated_at=NOW),
        current.updated_at,
    )
    with pytest.raises(ValueError, match="stale or cross-research"):
        service.handle(
            {
                "type": "resolve_confirm",
                "research_id": "r-card",
                "decision": "reject_keep_logic",
                "request_id": "card-a",
                "command_id": "cmd-stale",
                "expected_revision": service.store.revision_of("r-card"),
            }
        )


def test_cross_research_card_is_rejected(tmp_path: Path) -> None:
    service = _service(tmp_path)
    for research_id, request_id in (("r-a", "card-a"), ("r-b", "card-b")):
        service.store.create(
            replace(
                new_research(research_id, NOW),
                status=ResearchStatus.AWAITING_CONFIRM,
                pending_confirm=ConfirmRequest(
                    request_id=request_id,
                    kind=ConfirmKind.COVERAGE,
                    proposed_change="改",
                    reason="原因",
                    effect="影响",
                    created_at=NOW,
                ),
            )
        )
    with pytest.raises(ValueError, match="stale or cross-research"):
        service.handle(
            {
                "type": "resolve_confirm",
                "research_id": "r-b",
                "decision": "reject_keep_logic",
                "request_id": "card-a",
                "card_research_id": "r-a",
            }
        )
    assert service.store.load("r-b").pending_confirm.request_id == "card-b"


def test_coverage_or_economic_confirm_opens_a_version_and_keeps_the_audit(tmp_path: Path) -> None:
    service = _service(tmp_path)
    base = replace(new_research("r-ver", NOW), brief=locked_brief())
    opened = transition(base, ResearchEvent.CONFIRM_RUN, NOW)
    audit_row = Reverification("old-round", "pit.consistency", None, False, NOW, version_number=1)
    opened = replace(opened, reverifications=(audit_row,), reverification_audit=(audit_row,))
    pending = ConfirmRequest(
        request_id="card-cov",
        kind=ConfirmKind.COVERAGE,
        proposed_change="改前：覆盖底线 改后：更低",
        reason="覆盖不足",
        effect="开新版",
        patch=(("coverage_floor", {"min_assets": 1, "min_years": 1, "max_missing_pct": 50}),),
        created_at=NOW,
    )
    awaiting = replace(opened, status=ResearchStatus.AWAITING_CONFIRM, pending_confirm=pending)
    service.store.create(awaiting)
    service.handle(
        {
            "type": "resolve_confirm",
            "research_id": "r-ver",
            "decision": "accept_lower_floor",
            "request_id": "card-cov",
        }
    )
    loaded = service.store.load("r-ver")
    assert loaded.current_version_number == 2
    assert loaded.versions[0].version_id.endswith("-v1")
    assert loaded.reverifications == ()
    assert loaded.reverification_audit[0].round_id == "old-round"


def test_pause_text_and_button_leave_the_same_state(tmp_path: Path) -> None:
    service = _service(tmp_path)
    brief = locked_brief()
    for research_id, message, kind in (
        ("r-button", None, "pause"),
        ("r-zh", "暂停", "send_dialogue"),
        ("r-en", "pause", "send_dialogue"),
    ):
        service.store.create(
            replace(new_research(research_id, NOW), status=ResearchStatus.RUNNING, brief=brief)
        )
        if kind == "pause":
            service.handle({"type": "pause", "research_id": research_id})
        else:
            service.handle({"type": "send_dialogue", "research_id": research_id, "message": message})
        loaded = service.store.load(research_id)
        assert loaded.status is ResearchStatus.PAUSED
        assert loaded.brief == brief


def test_pit_reverify_blocks_only_dependent_packs(tmp_path: Path) -> None:
    research = completed_research()
    current = research.versions[-1].rounds[-1].round_id
    pit_fail = Reverification(current, "pit.consistency", None, False, NOW, version_number=1)
    old_fail = Reverification("old-round", "pit.consistency", None, False, NOW, version_number=1)
    dependent = ExportRecord(
        "pack-current",
        ExportKind.STRATEGY_PACK,
        str(tmp_path / "current.zip"),
        1,
        NOW,
        (),
        False,
        round_id=current,
    )
    other = ExportRecord(
        "pack-other",
        ExportKind.STRATEGY_PACK,
        str(tmp_path / "other.zip"),
        1,
        NOW,
        (),
        False,
        round_id="old-round",
    )
    unlabeled = ExportRecord(
        "pack-unknown",
        ExportKind.STRATEGY_PACK,
        str(tmp_path / "unknown.zip"),
        1,
        NOW,
        (),
        False,
    )
    record = ExportRecord(
        "record",
        ExportKind.RESEARCH_RECORD,
        str(tmp_path / "record.zip"),
        1,
        NOW,
        (),
        False,
    )
    original_pass = replace(research, exports=(dependent, other, unlabeled, record))
    eligibility = strategy_pack_eligibility(original_pass)
    assert eligibility.eligible is True
    assert "pit_executed_and_passed" not in eligibility.failed_checks

    blocked = strategy_pack_eligibility(replace(original_pass, reverifications=(pit_fail,)))
    assert blocked.eligible is False
    assert "all_reverifies_passed" in blocked.failed_checks
    assert "pit_executed_and_passed" not in blocked.failed_checks

    from engine.export import mark_exports_overturned

    marked = mark_exports_overturned(replace(original_pass, reverifications=(pit_fail,)), pit_fail)
    by_id = {item.export_id: item for item in marked.exports}
    assert by_id["pack-current"].overturned is True
    assert by_id["pack-other"].overturned is False
    assert by_id["pack-unknown"].overturned is False
    assert by_id["pack-unknown"].association == "pending"
    assert by_id["record"].overturned is False

    unrelated = mark_exports_overturned(replace(original_pass, reverifications=(old_fail,)), old_fail)
    unrelated_ids = {item.export_id: item for item in unrelated.exports}
    assert unrelated_ids["pack-current"].overturned is False
    assert unrelated_ids["pack-other"].overturned is True
    assert unrelated.export_eligible is True
    assert strategy_pack_eligibility(unrelated).eligible is True


def test_five_bools_pass_but_low_coverage_refuses_strategy_pack(tmp_path: Path) -> None:
    service = _service(tmp_path)
    floor = CoverageFloor(5, 1, 10.0)
    brief = replace(
        completed_research().brief,
        coverage_floor=Slot(floor, True),
    )
    research = replace(
        completed_research(),
        research_id="r-cov",
        brief=brief,
        last_coverage=CoverageSnapshot(
            ("AAA",),
            3.0,
            0.0,
            date(2020, 1, 2),
            date(2024, 1, 2),
            NOW,
        ),
    )
    eligibility = strategy_pack_eligibility(research)
    assert eligibility.eligible is False
    assert eligibility.failed_checks == ("coverage_satisfied",)
    assert "缺少" not in " ".join(eligibility.reasons)
    assert "覆盖低于冻结底线" in eligibility.reasons
    service.store.create(research)
    with pytest.raises(ValueError, match="coverage_satisfied"):
        service.handle(
            {"type": "export_artifact", "research_id": "r-cov", "kind": "strategy_pack"}
        )
    assert list(Path(tmp_path).rglob("*.zip")) == []
    refused = service.store.connection.execute(
        "SELECT kind FROM research_event WHERE research_id=?",
        ("r-cov",),
    ).fetchall()
    assert any(row[0] == "export_refused" for row in refused)


def test_missing_coverage_measurement_keeps_the_reason(tmp_path: Path) -> None:
    floor = CoverageFloor(1, 1, 10.0)
    research = replace(
        completed_research(),
        brief=replace(completed_research().brief, coverage_floor=Slot(floor, True)),
        last_coverage=None,
    )
    eligibility = strategy_pack_eligibility(research)
    assert "coverage_satisfied" in eligibility.failed_checks
    assert "缺少覆盖实测值" in eligibility.reasons


def test_reverify_does_not_add_a_round_or_window_m(tmp_path: Path) -> None:
    index = pd.bdate_range("2020-01-02", periods=40)
    frame = pd.DataFrame(
        {"AAA": range(40, 80), "BBB": range(20, 60), "__benchmark__": range(100, 140)},
        index=index,
    )
    snapshot = tmp_path / "snap.csv"
    frame.to_csv(snapshot, index_label="date")
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "material_id": "local:note",
                "source": "local",
                "title": "note",
                "url": "",
                "text": "undated",
                "fetched_at": "2020-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    research = completed_research()
    attempt = research.versions[0].rounds[0].accepted_attempt
    updated_attempt = replace(attempt, data_snapshot_path=snapshot, evidence_paths=(evidence,))
    research = replace(
        research,
        research_id="r-rev",
        versions=(
            replace(
                research.versions[0],
                rounds=(
                    replace(
                        research.versions[0].rounds[0],
                        accepted_attempt=updated_attempt,
                    ),
                ),
            ),
        ),
    )
    from engine.research.data_window import cumulative_rounds_on_window

    before_rounds = len(research.versions[-1].rounds)
    before_m = cumulative_rounds_on_window(research)
    before_budget = research.implementation_trial_budget
    service = _service(tmp_path)
    service.store.create(research)
    service.handle(
        {
            "type": "reverify",
            "research_id": "r-rev",
            "round_id": research.versions[-1].rounds[-1].round_id,
            "method_id": "scorecard.market",
        }
    )
    loaded = service.store.load("r-rev")
    assert len(loaded.versions[-1].rounds) == before_rounds
    assert cumulative_rounds_on_window(loaded) == before_m
    assert loaded.implementation_trial_budget == before_budget
    assert loaded.reverifications[-1].method_id == "scorecard.market"
    assert loaded.reverifications[-1].input_hash


def test_ambiguous_reverify_offers_choices_and_does_not_run(tmp_path: Path) -> None:
    research = completed_research()
    first = research.versions[0].rounds[0]
    second = replace(first, round_id="r-export-v1-r2", number=2)
    research = replace(
        research,
        research_id="r-amb",
        versions=(replace(research.versions[0], rounds=(first, second)),),
    )
    updated = apply_runtime_dialogue(research, "重验上一轮的稳定性", NOW, perform=None)
    assert updated is not None
    assert updated.reverifications == ()
    assert "r-export-v1-r1" in updated.dialogue[-1].text
    assert "r-export-v1-r2" in updated.dialogue[-1].text
    assert "请选择" in updated.dialogue[-1].text


def _executable_body(threshold: float, pass_value: float, fail_value: float) -> str:
    return json.dumps(
        {
            "executable": True,
            "operator": "threshold",
            "threshold": threshold,
            "comparison": ">=",
            "samples": [
                {"name": "pass", "input": {"value": pass_value}, "expect_pass": True},
                {"name": "fail", "input": {"value": fail_value}, "expect_pass": False},
            ],
        }
    )


def test_method_revision_reverify_uses_the_frozen_threshold(tmp_path: Path) -> None:
    service = _service(tmp_path)
    old = create_method(
        service.store,
        "custom.threshold",
        "阈值",
        "old",
        _executable_body(1.0, 1.5, 0.2),
        MethodSource.DEPOSITED,
        NOW,
    )
    revised = revise_method(
        service.store,
        "custom.threshold",
        "阈值",
        "new",
        _executable_body(5.0, 6.0, 2.0),
        datetime(2026, 11, 3, tzinfo=UTC),
    )
    assert execute_method_revision(service.store, old.method_id, old.revision_hash, 2.0) is True
    assert execute_method_revision(service.store, revised.method_id, revised.revision_hash, 2.0) is False
    with pytest.raises(ValueError, match="unregistered method revision"):
        execute_method_revision(service.store, old.method_id, "not-a-revision", 2.0)
    with pytest.raises(ValueError, match="golden"):
        create_method(
            service.store,
            "custom.bare",
            "裸",
            "no samples",
            json.dumps({"executable": True, "threshold": 1}),
            MethodSource.DEPOSITED,
            NOW,
        )
    suggestion = create_method(
        service.store,
        "custom.kalman",
        "卡尔曼",
        "unimplemented",
        json.dumps({"executable": False}),
        MethodSource.DEPOSITED,
        NOW,
    )
    with pytest.raises(ValueError, match="cannot be executed"):
        execute_method_revision(service.store, suggestion.method_id, suggestion.revision_hash, 1.0)

    class _Sim:
        sharpe = 2.0

    class _Spec:
        method_set = (MethodRef(old.method_id, old.revision_hash),)

    attempt = Attempt(
        "a-custom",
        1,
        ChangeClass.PARAM,
        _Spec(),
        _Sim(),
        VerificationReport(()),
        ReviewReport(True, ()),
    )
    round_ = RoundV2(
        "round-custom",
        1,
        attempt,
        NOW,
        LogicStatement("custom", False, baseline_version=1),
        ImplementationDelta(),
        TrialCounters(1, 0, 1),
    )
    version = Version("r-custom-v1", 1, locked_brief(), (round_,), NOW, "confirm_run")
    research = replace(
        new_research("r-custom", NOW),
        status=ResearchStatus.COMPLETED,
        brief=locked_brief(),
        versions=(version,),
        current_version_number=1,
    )
    rerun = reverify_round(
        research,
        {"round_id": "round-custom", "method_id": old.method_id},
        NOW,
        service.store,
    )
    assert rerun.reverifications[-1].passed is True
    assert rerun.reverifications[-1].revision == old.revision_hash
    assert len(rerun.versions[-1].rounds) == 1

    class _NewSpec:
        method_set = (MethodRef(revised.method_id, revised.revision_hash),)

    other = replace(
        research,
        research_id="r-other",
        versions=(
            replace(
                version,
                version_id="r-other-v1",
                rounds=(
                    replace(
                        round_,
                        round_id="round-other",
                        accepted_attempt=replace(attempt, spec=_NewSpec()),
                    ),
                ),
            ),
        ),
    )
    explicit = reverify_round(
        other,
        {"round_id": "round-other", "method_id": revised.method_id, "revision": revised.revision_hash},
        NOW,
        service.store,
    )
    assert explicit.reverifications[-1].passed is False
    assert explicit.reverifications[-1].revision == revised.revision_hash
    with pytest.raises(ValueError, match="unregistered method revision"):
        reverify_round(
            research,
            {"round_id": "round-custom", "method_id": old.method_id, "revision": revised.revision_hash},
            NOW,
            service.store,
        )

    plain = replace(completed_research(), research_id="r-suggest")
    service.store.create(plain)
    service.handle({"type": "send_dialogue", "research_id": "r-suggest", "message": "建议方法 custom"})
    reply = service.store.load("r-suggest").dialogue[-1].text
    executable, _, suggestions = reply.partition("建议（不能执行或计作通过）")
    assert f"{old.method_id}@{revised.revision_hash}" in executable
    assert "custom.kalman" in suggestions
    assert "custom.kalman@" not in executable


def test_publish_stages_then_authorizes_and_recovers_only_with_a_matching_row(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research = replace(completed_research(), research_id="r-pub")
    service.store.create(research)
    command_id = "export-cmd-1"
    payload = service.handle(
        {
            "type": "export_artifact",
            "research_id": "r-pub",
            "kind": "research_record",
            "command_id": command_id,
            "expected_revision": 0,
        }
    )
    visible = Path(payload["path"])
    assert visible.is_file()
    assert command_id in str(visible)
    fingerprint = payload["fingerprint"]
    again = service.handle(
        {
            "type": "export_artifact",
            "research_id": "r-pub",
            "kind": "research_record",
            "command_id": command_id,
            "expected_revision": 0,
        }
    )
    loaded = service.store.load("r-pub")
    assert again["path"] == payload["path"]
    assert again["fingerprint"] == fingerprint
    assert len(loaded.exports) == 1
    assert loaded.exports[0].fingerprint == fingerprint

    crashed = replace(completed_research(), research_id="r-crash")
    service.store.create(crashed)
    os.environ["ALPHALOOP_EXPORT_CRASH_AFTER_AUTHORIZE"] = "1"
    try:
        with pytest.raises(RuntimeError, match="injected crash"):
            service.handle(
                {
                    "type": "export_artifact",
                    "research_id": "r-crash",
                    "kind": "research_record",
                    "command_id": "export-crash",
                    "expected_revision": 0,
                }
            )
    finally:
        os.environ.pop("ALPHALOOP_EXPORT_CRASH_AFTER_AUTHORIZE", None)
    assert service.store.load("r-crash").exports == ()
    crash_visible = list((tmp_path / "exports").rglob("*")) if (tmp_path / "exports").exists() else []
    assert not any("export-crash" in path.name or "export-crash" in str(path.parent) for path in crash_visible)
    restored = service.handle(
        {
            "type": "export_artifact",
            "research_id": "r-crash",
            "kind": "research_record",
            "command_id": "export-crash",
            "expected_revision": 0,
        }
    )
    crash_loaded = service.store.load("r-crash")
    assert len(crash_loaded.exports) == 1
    assert crash_loaded.exports[0].export_id == "export-crash"
    assert Path(restored["path"]).is_file()
    service.handle(
        {
            "type": "export_artifact",
            "research_id": "r-crash",
            "kind": "research_record",
            "command_id": "export-crash",
            "expected_revision": 0,
        }
    )
    assert len(service.store.load("r-crash").exports) == 1

    auth = service.store.get_publish_authorization("r-crash", "export-crash")
    assert auth is not None
    Path(auth["final_path"]).unlink()
    private = Path(auth["private_path"])
    if private.exists():
        private.unlink()
    with service.store.connection:
        service.store.connection.execute(
            "DELETE FROM command_receipt WHERE research_id=? AND command_id=?",
            ("r-crash", "export-crash"),
        )
    with pytest.raises(ValueError, match="missing file"):
        service.handle(
            {
                "type": "export_artifact",
                "research_id": "r-crash",
                "kind": "research_record",
                "command_id": "export-crash",
                "expected_revision": service.store.revision_of("r-crash"),
            }
        )


def test_private_pack_is_not_published_when_recheck_fails(tmp_path: Path) -> None:
    index = pd.bdate_range("2020-01-02", periods=40)
    frame = pd.DataFrame(
        {"AAA": range(40, 80), "BBB": range(20, 60), "__benchmark__": range(100, 140)},
        index=index,
    )
    snapshot = tmp_path / "prices.csv"
    frame.to_csv(snapshot, index_label="date")
    research = completed_research()
    attempt = research.versions[0].rounds[0].accepted_attempt
    research = replace(
        research,
        research_id="r-pit",
        versions=(
            replace(
                research.versions[0],
                rounds=(
                    replace(
                        research.versions[0].rounds[0],
                        accepted_attempt=replace(attempt, data_snapshot_path=snapshot),
                    ),
                ),
            ),
        ),
    )
    service = _service(tmp_path)
    service.store.create(research)
    os.environ["ALPHALOOP_EXPORT_RECHECK_FAIL"] = "pit_executed_and_passed"
    try:
        with pytest.raises(ValueError, match="pit_executed_and_passed"):
            service.handle(
                {
                    "type": "export_artifact",
                    "research_id": "r-pit",
                    "kind": "strategy_pack",
                    "command_id": "pack-race",
                    "expected_revision": 0,
                }
            )
    finally:
        os.environ.pop("ALPHALOOP_EXPORT_RECHECK_FAIL", None)
    visible = tmp_path / "exports"
    assert not visible.exists() or list(visible.rglob("*.zip")) == []
    assert service.store.get_publish_authorization("r-pit", "pack-race") is None
    from engine.research.publish import recover_publish

    recovered = recover_publish(service.store, service.store.load("r-pit"))
    assert recovered.exports == ()
    assert not visible.exists() or list(visible.rglob("*.zip")) == []


def test_continue_iterate_same_params_consumes_this_version_quota(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from engine.research.clock import TimeBudget
    from engine.research.honest_stop import trial_budget_increment
    from engine.research.loop import ResearchLoop
    from tests.test_cumulative_trials import FailTwiceThenPassBuilder
    from tests.test_loop_runtime import NOW as LOOP_NOW
    from tests.test_loop_runtime import PassReviewer, running_research

    monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "1")
    service = _service(tmp_path)
    service.store.create(running_research())
    loop = ResearchLoop(
        service.store,
        FailTwiceThenPassBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: LOOP_NOW,
    )
    completed = loop.run_once("r-loop")
    assert completed.status is ResearchStatus.COMPLETED
    versions = len(completed.versions)
    budget = completed.implementation_trial_budget
    brief = completed.brief
    rounds = len(completed.versions[-1].rounds)
    service.handle(
        {"type": "continue_iterate", "research_id": "r-loop", "user_confirmed": True}
    )
    loaded = service.store.load("r-loop")
    assert loaded.status is ResearchStatus.RUNNING
    assert len(loaded.versions) == versions
    assert loaded.current_version_number == completed.current_version_number
    assert loaded.brief == brief
    assert len(loaded.versions[-1].rounds) == rounds
    assert loaded.implementation_trial_budget == budget + trial_budget_increment()


def test_dialogue_export_lists_checks_without_writing_a_pack(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research = replace(completed_research(), research_id="r-ask-export")
    service.store.create(research)
    service.handle({"type": "send_dialogue", "research_id": "r-ask-export", "message": "导出"})
    loaded = service.store.load("r-ask-export")
    assert loaded.exports == ()
    assert "strategy_pack" in loaded.dialogue[-1].text
    assert "research_record" in loaded.dialogue[-1].text
    english = apply_runtime_dialogue(research, "which gate failed", NOW)
    assert english is not None
    assert english.status is research.status
