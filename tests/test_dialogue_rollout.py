"""PR6 enablement: default off, write gate, backup, unknown revisions."""

from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.dialogue.actions import MISSING
from engine.main import ResearchCommandService
from engine.research.candidates import SOFTWARE_CANDIDATE_DEFAULTS
from engine.research.clock import TimeBudget
from engine.research.dialogue_rollout import (
    DIALOGUE_V2_KEY,
    audit_and_trip,
    create_upgrade_backup,
    dialogue_v2_enabled,
    new_dialogue_writes_open,
    note_unauthorized_execution,
    pause_if_unknown_revision,
    restore_upgrade_backup,
    seal_snapshot,
    trip_write_gate,
    version_open_guard,
    write_dialogue_enabled,
    write_gate,
)
from engine.research.loop import ResearchLoop
from engine.research.models import MethodRef, ResearchStatus, Slot, new_research
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def _service(tmp_path: Path) -> ResearchCommandService:
    tmp_path.mkdir(parents=True, exist_ok=True)
    return ResearchCommandService(
        SQLiteStore(tmp_path / "research.db"),
        EnginePaths.for_colocated_root(tmp_path),
    )


class _Boom:
    def build(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("builder should not run for an unknown revision")

    def retry(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("retry")

    def next_change(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("next")


@pytest.mark.dialogue_product_default
def test_packaged_default_is_off_and_old_slots_and_buttons_still_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALPHALOOP_DIALOGUE_V2", raising=False)
    assert dialogue_v2_enabled(tmp_path / "settings.json") is False
    service = _service(tmp_path)
    created = service.handle({"type": "create_draft"})
    research_id = created["research_id"]
    service.handle(
        {"type": "send_dialogue", "research_id": research_id, "message": "美股股票的均值回归"}
    )
    service.handle({"type": "send_dialogue", "research_id": research_id, "message": "6小时"})
    loaded = service.store.load(research_id)
    assert loaded.status is ResearchStatus.DRAFT
    assert loaded.brief.max_effective_hours.value == pytest.approx(6)
    assert loaded.active_proposal is None

    running_id = "r-buttons"
    service.store.create(replace(new_research(running_id, NOW), status=ResearchStatus.RUNNING))
    service.handle({"type": "send_dialogue", "research_id": running_id, "message": "现在在做什么"})
    asked = service.store.load(running_id)
    assert asked.status is ResearchStatus.RUNNING
    assert MISSING not in asked.dialogue[-1].text
    service.handle({"type": "pause", "research_id": running_id})
    assert service.store.load(running_id).status is ResearchStatus.PAUSED


def test_settings_boolean_wins_over_the_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHALOOP_DIALOGUE_V2", "1")
    path = tmp_path / "settings.json"
    write_dialogue_enabled(path, False)
    assert dialogue_v2_enabled(path) is False
    write_dialogue_enabled(path, True)
    assert json.loads(path.read_text(encoding="utf-8"))[DIALOGUE_V2_KEY] is True
    assert dialogue_v2_enabled(path) is True


def test_enabled_flag_restores_runtime_answers(tmp_path: Path) -> None:
    service = _service(tmp_path)
    write_dialogue_enabled(service.paths.data.settings_file, True)
    research_id = "r-on"
    service.store.create(replace(new_research(research_id, NOW), status=ResearchStatus.RUNNING))
    service.handle({"type": "send_dialogue", "research_id": research_id, "message": "现在在做什么"})
    reply = service.store.load(research_id).dialogue[-1].text
    assert "允许的命令" in reply
    assert service.store.load(research_id).status is ResearchStatus.RUNNING


def test_write_gate_closes_new_dialogue_and_keeps_the_journal(tmp_path: Path) -> None:
    service = _service(tmp_path)
    write_dialogue_enabled(service.paths.data.settings_file, True)
    created = service.handle(
        {"type": "create_draft", "research_id": "r-journal", "command_id": "create-journal"}
    )
    assert created["research_id"] == "r-journal"
    assert trip_write_gate(service.store, "unauthorized_execution", "forged tool") is True
    assert trip_write_gate(service.store, "duplicate_m", "ignored") is False
    assert write_gate(service.store)["reason"] == "unauthorized_execution"
    assert new_dialogue_writes_open(service.store, service.paths.data.settings_file) is False
    before = service.store.connection.execute(
        "SELECT COUNT(*) FROM command_receipt"
    ).fetchone()
    service.handle({"type": "send_dialogue", "research_id": "r-journal", "message": "现在在做什么"})
    loaded = service.store.load("r-journal")
    assert loaded.active_proposal is None
    assert "允许的命令" not in loaded.dialogue[-1].text
    after = service.store.connection.execute("SELECT COUNT(*) FROM command_receipt").fetchone()
    events = service.store.connection.execute(
        "SELECT COUNT(*) FROM research_event WHERE research_id=?",
        ("r-journal",),
    ).fetchone()
    assert before is not None and after is not None and int(after[0]) >= int(before[0])
    assert events is not None and int(events[0]) >= 1
    gate_file = tmp_path / "dialogue-write-gate.json"
    assert json.loads(gate_file.read_text(encoding="utf-8"))["closed"] is True


def test_each_kill_reason_can_close_the_gate(tmp_path: Path) -> None:
    service = _service(tmp_path)
    note_unauthorized_execution(service.store, "shell")
    assert write_gate(service.store)["reason"] == "unauthorized_execution"

    other = _service(tmp_path / "version")
    with version_open_guard(other.store, "r", "cmd-open", NOW):
        pass
    with pytest.raises(UserFacingError) as caught, version_open_guard(other.store, "r", "cmd-open", NOW):
        pass
    assert caught.value.code == "DUPLICATE_OPEN_VERSION"
    assert write_gate(other.store)["reason"] == "duplicate_open_version"

    resend = _service(tmp_path / "resend")
    from engine.research.dialogue_rollout import note_unauthorized_resend

    note_unauthorized_resend(resend.store, "cmd-unknown")
    assert write_gate(resend.store)["reason"] == "unauthorized_resend"

    duplicate = _service(tmp_path / "m")
    duplicate.store.connection.execute(
        """
        INSERT INTO window_round_ledger(research_id, version_number, round_number, round_id, window_key)
        VALUES('r', 1, 1, 'round-1', 'window-a')
        """
    )
    duplicate.store.connection.execute(
        """
        INSERT INTO data_window_round_counts(window_key, cumulative_rounds) VALUES('window-a', 2)
        """
    )
    duplicate.store.connection.commit()
    assert audit_and_trip(duplicate.store) == "duplicate_m"

    drift = _service(tmp_path / "drift")
    snapshot = tmp_path / "drift" / "snapshots" / "prices.csv"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("open\n", encoding="utf-8")
    seal_snapshot(drift.store, "r-drift", snapshot)
    snapshot.write_text("changed\n", encoding="utf-8")
    assert audit_and_trip(drift.store) == "frozen_data_drift"

    lost = _service(tmp_path / "lost")
    lost.store.connection.execute(
        """
        INSERT INTO committed_round(
            research_id, version_number, round_number, round_id, attempt_id, candidate_hash
        ) VALUES('r', 1, 1, 'round-lost', 'attempt', 'hash')
        """
    )
    lost.store.connection.commit()
    assert audit_and_trip(lost.store) == "lost_committed_receipt"


def test_failed_version_open_releases_the_claim(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(RuntimeError), version_open_guard(service.store, "r", "cmd-once", NOW):
        raise RuntimeError("boom")
    with version_open_guard(service.store, "r", "cmd-once", NOW):
        pass
    assert write_gate(service.store) is None


def test_unknown_planner_revision_pauses_before_the_builder(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "research.db")
    research = replace(
        new_research("r-unknown", NOW),
        status=ResearchStatus.RUNNING,
        candidate_policy=replace(SOFTWARE_CANDIDATE_DEFAULTS, policy_version="candidate-policy-v9"),
    )
    store.create(research)
    loop = ResearchLoop(
        store,
        _Boom(),  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        TimeBudget(time.monotonic),
        lambda: NOW,
    )
    paused = loop.run_once("r-unknown")
    assert paused.status is ResearchStatus.PAUSED
    assert paused.candidate_policy is not None
    assert paused.candidate_policy.policy_version == "candidate-policy-v9"
    assert paused.last_run_error_code == "UNKNOWN_REVISION"
    known = replace(
        research,
        candidate_policy=SOFTWARE_CANDIDATE_DEFAULTS,
        brief=replace(research.brief, round1_methods=Slot((MethodRef("overfit.walk", "walk-v1"),), True)),
    )
    assert pause_if_unknown_revision(store, known, NOW) is None


def test_upgrade_backup_restores_into_a_temp_dir(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.store.create(new_research("r-backup", NOW))
    snapshot = tmp_path / "snapshots" / "frozen.csv"
    snapshot.parent.mkdir()
    snapshot.write_text("price,1\n", encoding="utf-8")
    seal_snapshot(service.store, "r-backup", snapshot)
    backup = tmp_path / "backup"
    manifest = create_upgrade_backup(service.store, backup)
    assert manifest["integrity"] == "ok"
    assert manifest["files"]
    snapshot.write_text("mutated\n", encoding="utf-8")
    report = restore_upgrade_backup(backup, tmp_path / "restored")
    assert report["integrity"] == "ok"
    assert report["journal"] == "command_receipt"
    assert report["researches"] == 1
    restored = (tmp_path / "restored" / "frozen.csv").read_text(encoding="utf-8")
    assert restored == "price,1\n"
    assert (tmp_path / "snapshots" / "frozen.csv").read_text(encoding="utf-8") == "mutated\n"
