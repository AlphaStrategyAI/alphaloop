"""Command receipts, revision conflicts, and the 0.9.5 journal migration."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import jsonschema
import pandas as pd
import pytest

from engine.main import ResearchCommandService
from engine.research.command_journal import (
    COMMAND_PAYLOAD_CONFLICT,
    CREATE_SOURCE_CONFLICT,
    NEW_PROPOSAL_REQUIRES_CURRENT_CLIENT,
    REMOTE_UNKNOWN_NEEDS_AUTH,
    REVISION_CONFLICT,
)
from engine.research.models import (
    AssetClass,
    ExportKind,
    ExportRecord,
    Market,
    ResearchStatus,
    Reverification,
    Slot,
    Universe,
    new_research,
)
from engine.research.pool_data_shrink import set_pool_data_loader
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError
from tests.fixtures.pool_loader import AllSymbolsAvailableLoader
from tests.test_state_machine import locked_brief

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "contracts" / "desktop-api.schema.json").read_text(encoding="utf-8"))

# 0.9.5 tables, before revision / research_event / command_receipt.
OLD_SCHEMA = """
CREATE TABLE researches (
    research_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_completed_round INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE engine_heartbeat (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    owner TEXT NOT NULL,
    pid INTEGER NOT NULL,
    heartbeat_at TEXT NOT NULL
);
CREATE TABLE review_attempts (
    attempt_id TEXT PRIMARY KEY,
    research_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    attempt_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE method_revisions (
    method_id TEXT NOT NULL,
    revision_hash TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL,
    body TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'preset',
    deposited_from_research_id TEXT,
    supersedes TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (method_id, revision_hash)
);
CREATE TABLE method_usage (
    method_id TEXT NOT NULL,
    revision_hash TEXT NOT NULL,
    research_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    PRIMARY KEY (method_id, revision_hash, research_id, version_number)
);
CREATE TABLE engine_errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_id TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE data_window_round_counts (
    window_key TEXT PRIMARY KEY,
    cumulative_rounds INTEGER NOT NULL
);
"""


def _service(tmp_path: Path) -> ResearchCommandService:
    store = SQLiteStore(tmp_path / "journal.db")
    return ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))


def _state_json(store: SQLiteStore, research_id: str) -> str:
    row = store.connection.execute(
        "SELECT state_json FROM researches WHERE research_id=?",
        (research_id,),
    ).fetchone()
    assert row is not None
    return str(row[0])


def _events(store: SQLiteStore, research_id: str) -> list[tuple[int, str]]:
    rows = store.connection.execute(
        "SELECT seq, kind FROM research_event WHERE research_id=? ORDER BY seq",
        (research_id,),
    ).fetchall()
    return [(int(seq), str(kind)) for seq, kind in rows]


def _dialogue(service: ResearchCommandService, research_id: str, message: str, revision: int, command_id: str):
    return service.handle(
        {
            "type": "send_dialogue",
            "research_id": research_id,
            "message": message,
            "command_id": command_id,
            "expected_revision": revision,
        }
    )


def _create(service: ResearchCommandService, research_id: str, command_id: str) -> dict:
    return service.handle(
        {
            "type": "create_draft",
            "research_id": research_id,
            "command_id": command_id,
        }
    )


class _FrozenClock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment


class _BlockingLoader:
    def __init__(self) -> None:
        self.calls = 0
        self.entered = threading.Event()
        self.release = threading.Event()
        self.on_enter = None

    def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
        self.calls += 1
        if self.on_enter is not None:
            self.on_enter()
        self.entered.set()
        assert self.release.wait(timeout=5)
        index = pd.to_datetime([start, end])
        return pd.DataFrame(
            {symbol: pd.Series([100.0, 101.0], index=index, name=symbol) for symbol in symbols}
        )


class _CountingLoader:
    def __init__(self) -> None:
        self.calls = 0

    def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
        self.calls += 1
        return AllSymbolsAvailableLoader().load_daily(symbols, start, end)


def _runnable(store: SQLiteStore, research_id: str) -> None:
    from engine.research.symbol_pool import pool_for_market

    pool = pool_for_market(Market.US, AssetClass.EQUITY, AssetClass.EQUITY)
    assert pool is not None
    brief = locked_brief()
    universe = Universe(
        Market.US,
        AssetClass.EQUITY,
        AssetClass.EQUITY,
        pool.symbols,
        symbol_list_version=pool.version_id,
        user_symbols_override=False,
    )
    brief = replace(brief, universe=Slot(universe, True))
    research = replace(new_research(research_id, NOW), brief=brief)
    store.create(research)


def _confirm(service: ResearchCommandService, research_id: str, command_id: str, revision: int, **extra):
    body = {
        "type": "confirm_run",
        "research_id": research_id,
        "data_source_id": "yahoo_daily",
        "unlicensed_acknowledged": True,
        "command_id": command_id,
        "expected_revision": revision,
    }
    body.update(extra)
    return service.handle(body)


def test_migration_keeps_old_fields_trials_and_evidence_timestamps(tmp_path: Path) -> None:
    research = replace(
        new_research("r-old", NOW),
        implementation_trial_budget=7,
        exports=(
            ExportRecord(
                export_id="exp-1",
                kind=ExportKind.RESEARCH_RECORD,
                path="/tmp/r-old.zip",
                version_number=1,
                created_at=NOW,
                failed_checks=(),
            ),
        ),
        reverifications=(
            Reverification(
                round_id="round-1",
                method_id="pit.consistency",
                report={
                    "evidence_timestamps": [["doi:10.1000/x", "2019-05-01T00:00:00+00:00"]],
                    "trial_count": 4,
                },
                passed=True,
                created_at=NOW,
            ),
        ),
    )
    blob = SQLiteStore._encode(research)
    assert "2019-05-01T00:00:00+00:00" in blob
    assert '"implementation_trial_budget": 7' in blob or '"implementation_trial_budget":7' in blob
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.executescript(OLD_SCHEMA)
    raw.execute(
        "INSERT INTO researches(research_id, state_json, updated_at, last_completed_round) VALUES(?,?,?,?)",
        ("r-old", blob, NOW.isoformat(), 3),
    )
    raw.commit()
    raw.close()

    store = SQLiteStore(path)
    assert _state_json(store, "r-old") == blob
    loaded = store.load("r-old")
    assert loaded.implementation_trial_budget == 7
    assert loaded.reverifications[0].report["trial_count"] == 4
    assert loaded.reverifications[0].report["evidence_timestamps"][0][1] == "2019-05-01T00:00:00+00:00"
    assert loaded.exports[0].created_at == NOW
    assert store.revision_of("r-old") == 0
    assert _events(store, "r-old") == []

    again = SQLiteStore(path)
    assert _state_json(again, "r-old") == blob
    reread = again.load("r-old")
    assert reread.implementation_trial_budget == 7
    assert reread.reverifications[0].report["evidence_timestamps"] == loaded.reverifications[0].report["evidence_timestamps"]
    assert again.revision_of("r-old") == 0


def test_new_desktop_reads_revision_from_the_view_and_legacy_fetch_still_works(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = _create(service, "r-view", "c-view")
    assert created["revision"] == 0
    view = service.handle({"type": "fetch_view", "route": "#/research/r-view"})
    assert view["kind"] == "draft"
    assert view["revision"] == 0
    listed = service.handle({"type": "fetch_view", "route": "#/research"})
    assert listed["kind"] == "research_list"
    assert listed["rows"][0]["revision"] == 0
    legacy = service.handle({"type": "create_draft"})
    assert "research_id" in legacy
    assert service.store.revision_of(legacy["research_id"]) == 0


def test_lost_create_response_replays_to_one_row(tmp_path: Path) -> None:
    service = _service(tmp_path)
    request = {"type": "create_draft", "research_id": "r-one", "command_id": "c-one"}
    first = service.handle(request)
    restarted = ResearchCommandService(
        SQLiteStore(service.store.path),
        EnginePaths.for_colocated_root(tmp_path),
    )
    second = restarted.handle(request)
    assert second["research_id"] == first["research_id"] == "r-one"
    assert second["replayed"] is True
    assert len(restarted.store.list_research()) == 1


def test_create_stored_but_receipt_lost_restores_one_row(tmp_path: Path) -> None:
    service = _service(tmp_path)
    request = {"type": "create_draft", "research_id": "r-gap", "command_id": "c-gap"}
    service.handle(request)
    before = _state_json(service.store, "r-gap")
    with service.store.connection:
        service.store.connection.execute("DELETE FROM command_receipt")
    replayed = service.handle(request)
    assert replayed["research_id"] == "r-gap"
    assert len(service.store.list_research()) == 1
    assert _state_json(service.store, "r-gap") == before
    receipt = service.store.connection.execute(
        "SELECT status FROM command_receipt WHERE research_id=? AND command_id=?",
        ("r-gap", "c-gap"),
    ).fetchone()
    assert receipt[0] == "committed"


def test_unknown_create_source_does_not_overwrite(tmp_path: Path) -> None:
    service = _service(tmp_path)
    legacy = service.handle({"type": "create_draft"})
    research_id = legacy["research_id"]
    with pytest.raises(UserFacingError) as caught:
        service.handle(
            {
                "type": "create_draft",
                "research_id": research_id,
                "command_id": "c-other",
            }
        )
    assert caught.value.code == CREATE_SOURCE_CONFLICT
    assert len(service.store.list_research()) == 1


def test_double_click_returns_the_original_receipt(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _create(service, "r-dbl", "c-create")
    first = _dialogue(service, "r-dbl", "均值回归", 0, "c-dbl")
    second = _dialogue(service, "r-dbl", "均值回归", 0, "c-dbl")
    assert second["replayed"] is True
    assert second["revision"] == first["revision"]
    loaded = service.store.load("r-dbl")
    assert sum(1 for turn in loaded.dialogue if turn.role.value == "user") == 1
    assert service.store.revision_of("r-dbl") == first["revision"]


def test_same_command_id_with_a_different_payload_is_rejected(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _create(service, "r-pay", "c-create")
    _dialogue(service, "r-pay", "第一句", 0, "c-pay")
    with pytest.raises(UserFacingError) as caught:
        _dialogue(service, "r-pay", "另一句", 0, "c-pay")
    assert caught.value.code == COMMAND_PAYLOAD_CONFLICT
    loaded = service.store.load("r-pay")
    assert sum(1 for turn in loaded.dialogue if turn.role.value == "user") == 1


def test_revision_conflict_requires_a_new_command_id(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _create(service, "r-rev", "c-create")
    _dialogue(service, "r-rev", "第一句", 0, "c-1")
    with pytest.raises(UserFacingError) as stale:
        _dialogue(service, "r-rev", "第二句", 0, "c-2")
    assert stale.value.code == REVISION_CONFLICT
    assert stale.value.params["revision"] == service.store.revision_of("r-rev")
    with pytest.raises(UserFacingError) as reused:
        _dialogue(service, "r-rev", "第二句", stale.value.params["revision"], "c-2")
    assert reused.value.code == COMMAND_PAYLOAD_CONFLICT
    fresh = _dialogue(service, "r-rev", "第二句", service.store.revision_of("r-rev"), "c-3")
    assert fresh["revision"] == 2
    assert sum(1 for turn in service.store.load("r-rev").dialogue if turn.role.value == "user") == 2


def test_two_writes_in_the_same_second_keep_distinct_events(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    frozen = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("engine.main._command_now", _FrozenClock(frozen))
    service = _service(tmp_path)
    _create(service, "r-sec", "c-create")
    first = _dialogue(service, "r-sec", "第一句", 0, "c-a")
    second = _dialogue(service, "r-sec", "第二句", first["revision"], "c-b")
    assert second["revision"] == first["revision"] + 1
    stamps = service.store.connection.execute(
        "SELECT updated_at FROM researches WHERE research_id=?",
        ("r-sec",),
    ).fetchone()
    assert stamps[0] == frozen.isoformat()
    kinds = [kind for _seq, kind in _events(service.store, "r-sec")]
    assert kinds == ["create_draft", "send_dialogue", "send_dialogue"]
    assert service.store.load("r-sec").implementation_trial_budget == new_research("x", NOW).implementation_trial_budget


def test_two_clients_with_different_ids_one_write_wins(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _create(service, "r-race", "c-create")
    barrier = threading.Barrier(2)
    results: list[object] = []

    def worker(command_id: str, message: str) -> None:
        barrier.wait(timeout=5)
        try:
            results.append(_dialogue(service, "r-race", message, 0, command_id))
        except UserFacingError as error:
            results.append(error)

    threads = [
        threading.Thread(target=worker, args=("c-left", "左边")),
        threading.Thread(target=worker, args=("c-right", "右边")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    successes = [item for item in results if isinstance(item, dict)]
    conflicts = [item for item in results if isinstance(item, UserFacingError)]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert conflicts[0].code == REVISION_CONFLICT
    assert conflicts[0].params["revision"] == successes[0]["revision"]
    assert sum(1 for turn in service.store.load("r-race").dialogue if turn.role.value == "user") == 1


def test_confirm_after_source_ack_follows_the_bumped_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Picking Yahoo and ticking the box each bump revision. Confirm must expect the later one."""
    service = _service(tmp_path)
    _runnable(service.store, "r-src")
    monkeypatch.setattr("engine.main.ensure_runnable_universe", lambda item: item)
    before = service.view_for("#/research/r-src")["revision"]
    selected = service.handle(
        {
            "type": "set_price_source",
            "research_id": "r-src",
            "data_source_id": "yahoo_daily",
        }
    )
    acked = service.handle(
        {
            "type": "set_price_source",
            "research_id": "r-src",
            "data_source_id": "yahoo_daily",
            "unlicensed_acknowledged": True,
        }
    )
    assert selected["revision"] == before + 1
    assert acked["revision"] == selected["revision"] + 1
    with pytest.raises(UserFacingError) as stale:
        _confirm(service, "r-src", "c-stale", before)
    assert stale.value.code == REVISION_CONFLICT
    assert stale.value.params["revision"] == acked["revision"]
    assert service.store.load("r-src").status is ResearchStatus.DRAFT
    opened = _confirm(service, "r-src", "c-fresh", acked["revision"])
    assert opened["status"] == "running"
    assert opened["revision"] == acked["revision"] + 1


def test_legacy_client_cannot_approve_a_new_style_proposal(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _runnable(service.store, "r-prop")
    service.journal.record_open_proposal("r-prop", "prop-1", NOW)
    view = service.view_for("#/research/r-prop")
    assert view["kind"] in {"draft", "confirm_run"}
    assert "revision" in view
    with pytest.raises(UserFacingError) as caught:
        service.handle(
            {
                "type": "confirm_run",
                "research_id": "r-prop",
                "data_source_id": "yahoo_daily",
                "unlicensed_acknowledged": True,
            }
        )
    assert caught.value.code == NEW_PROPOSAL_REQUIRES_CURRENT_CLIENT
    assert service.store.load("r-prop").status is ResearchStatus.DRAFT
    revision = service.store.revision_of("r-prop")
    opened = _confirm(service, "r-prop", "c-approve", revision, reply_to="prop-1")
    assert opened["status"] == "running"
    assert len(service.store.load("r-prop").versions) == 1


def test_concurrent_confirm_run_creates_one_version(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _runnable(service.store, "r-go")
    loader = _BlockingLoader()
    set_pool_data_loader(loader)
    results: list[object] = []

    def worker(command_id: str) -> None:
        try:
            results.append(_confirm(service, "r-go", command_id, 0))
        except UserFacingError as error:
            results.append(error)

    first = threading.Thread(target=worker, args=("c-a",))
    second = threading.Thread(target=worker, args=("c-b",))
    first.start()
    assert loader.entered.wait(timeout=5)
    second.start()
    loader.release.set()
    first.join(timeout=5)
    second.join(timeout=5)
    assert loader.calls == 1
    loaded = service.store.load("r-go")
    assert loaded.status is ResearchStatus.RUNNING
    assert len(loaded.versions) == 1
    conflicts = [item for item in results if isinstance(item, UserFacingError)]
    assert any(item.code == REVISION_CONFLICT for item in conflicts)
    assert sum(isinstance(item, dict) for item in results) == 1


def test_inflight_confirm_returns_pending_and_replay_does_not_open_another_version(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _runnable(service.store, "r-pend")
    loader = _BlockingLoader()
    set_pool_data_loader(loader)
    outcome: dict[str, object] = {}

    def worker() -> None:
        try:
            outcome["first"] = _confirm(service, "r-pend", "c-same", 0)
        except UserFacingError as error:
            outcome["first"] = error

    thread = threading.Thread(target=worker)
    thread.start()
    assert loader.entered.wait(timeout=5)
    pending = _confirm(service, "r-pend", "c-same", 0)
    assert pending["status"] == "pending"
    assert pending["command_id"] == "c-same"
    loader.release.set()
    thread.join(timeout=5)
    assert loader.calls == 1
    replayed = _confirm(service, "r-pend", "c-same", 0)
    assert replayed["replayed"] is True
    assert loader.calls == 1
    assert len(service.store.load("r-pend").versions) == 1


def test_snapshot_change_during_probe_does_not_commit_and_replay_does_not_rebill(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _runnable(service.store, "r-snap")
    loader = _BlockingLoader()

    def bump() -> None:
        raw = sqlite3.connect(service.store.path)
        raw.execute("UPDATE researches SET revision = revision + 1 WHERE research_id=?", ("r-snap",))
        raw.commit()
        raw.close()

    loader.on_enter = bump
    loader.release.set()
    set_pool_data_loader(loader)
    with pytest.raises(UserFacingError) as caught:
        _confirm(service, "r-snap", "c-snap", 0)
    assert caught.value.code == REVISION_CONFLICT
    assert loader.calls == 1
    assert service.store.load("r-snap").status is ResearchStatus.DRAFT
    assert service.store.load("r-snap").versions == ()
    assert service.journal.reserved_budget("r-snap") == 1
    with pytest.raises(UserFacingError) as replayed:
        _confirm(service, "r-snap", "c-snap", 0)
    assert replayed.value.code == REVISION_CONFLICT
    assert loader.calls == 1


def test_unknown_remote_claim_is_not_rebilled_without_authorization(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _runnable(service.store, "r-unk")
    request = {
        "type": "confirm_run",
        "research_id": "r-unk",
        "data_source_id": "yahoo_daily",
        "unlicensed_acknowledged": True,
        "command_id": "c-unk",
        "expected_revision": 0,
    }
    head = service.store.research_head("r-unk")
    assert head is not None
    from engine.research.command_journal import payload_hash, state_snapshot

    service.journal.claim_remote(
        request,
        operation_key="confirm_run:r-unk:c-unk",
        budget_reserved=1,
        bound_revision=0,
        bound_version=None,
        bound_snapshot=state_snapshot(head[3]),
        now=NOW,
    )
    assert payload_hash(request)
    restarted = ResearchCommandService(
        SQLiteStore(service.store.path),
        EnginePaths.for_colocated_root(tmp_path),
    )
    counter = _CountingLoader()
    set_pool_data_loader(counter)
    with pytest.raises(UserFacingError) as killed:
        restarted.handle(request)
    assert killed.value.code == REMOTE_UNKNOWN_NEEDS_AUTH
    assert counter.calls == 0
    assert restarted.journal.reserved_budget("r-unk") == 1
    with pytest.raises(UserFacingError) as blocked:
        restarted.handle({**request, "command_id": "c-new"})
    assert blocked.value.code == REMOTE_UNKNOWN_NEEDS_AUTH
    assert counter.calls == 0
    assert restarted.journal.reserved_budget("r-unk") == 1
    opened = restarted.handle({**request, "command_id": "c-auth", "authorize_rebill": True})
    assert opened["status"] == "running"
    assert counter.calls == 1
    assert restarted.journal.reserved_budget("r-unk") == 2
    assert len(restarted.store.load("r-unk").versions) == 1


def test_send_dialogue_reply_without_envelope_is_rejected(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _create(service, "r-env", "c-create")
    with pytest.raises(UserFacingError) as caught:
        service.handle(
            {
                "type": "send_dialogue",
                "research_id": "r-env",
                "message": "好",
                "reply_to": "prop-x",
            }
        )
    assert caught.value.code == "COMMAND_ENVELOPE_REQUIRED"


def test_schema_keeps_legacy_writes_and_requires_the_new_dialogue_pair() -> None:
    jsonschema.validate({"type": "fetch_view", "route": "#/research"}, SCHEMA)
    jsonschema.validate(
        {"type": "send_dialogue", "research_id": "r", "message": "继续"},
        SCHEMA,
    )
    jsonschema.validate(
        {"type": "confirm_run", "research_id": "r"},
        SCHEMA,
    )
    jsonschema.validate(
        {
            "type": "send_dialogue",
            "research_id": "r",
            "message": "继续",
            "command_id": "c",
            "expected_revision": 1,
            "reply_to": "p",
        },
        SCHEMA,
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {"type": "send_dialogue", "research_id": "r", "message": "继续", "reply_to": "p"},
            SCHEMA,
        )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {"type": "create_draft", "research_id": "r"},
            SCHEMA,
        )


def test_english_methods_and_coverage_survive_a_leaked_read_transaction(tmp_path: Path) -> None:
    """The Windows e2e coverage reply hit ``database is locked``.

    A route poll's SELECT can leave a read transaction open. The next
    journaled write must still commit.
    """
    service = _service(tmp_path)
    _create(service, "r-en", "c-create")
    messages = (
        "Mean reversion on AAPL, a US stock, using daily prices.",
        "12 hours",
        "subperiod robustness check, out-of-sample stability, concentration, turnover cost",
        "at least 25 names, 10 years of history, and no more than 5% missing.",
    )
    revision = 0
    for index, message in enumerate(messages):
        service.store.connection._raw.execute("BEGIN")
        service.store.connection._raw.execute(
            "SELECT research_id FROM researches WHERE research_id=?",
            ("r-en",),
        ).fetchall()
        assert service.store.connection._raw.in_transaction
        result = service.handle(
            {
                "type": "send_dialogue",
                "research_id": "r-en",
                "message": message,
                "command_id": f"c-{index}",
                "expected_revision": revision,
                "locale": "en",
            }
        )
        revision = int(result["revision"])
        view = service.handle({"type": "fetch_view", "route": "#/research/r-en", "locale": "en"})
        assert view["revision"] == revision
    assert view["kind"] == "confirm_run"
    assert "25" in view["settings"]["coverage_floor"]
    assert "AAPL" in view["settings"]["universe_symbols"] or "AAPL" in str(view["settings"])


def test_journal_indexes_are_ready_for_timeline_reads(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "idx.db")
    names = {
        row[0]
        for row in store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
        ).fetchall()
    }
    assert {"research_event", "command_receipt", "idx_researches_status", "idx_research_event_research_seq"} <= names
    columns = {row[1] for row in store.connection.execute("PRAGMA table_info(researches)").fetchall()}
    assert {"revision", "last_seq", "status", "create_command_id"} <= columns
    store.create(new_research("r-idx", NOW))
    status = store.connection.execute(
        "SELECT status FROM researches WHERE research_id=?",
        ("r-idx",),
    ).fetchone()
    assert status[0] == "draft"
    plan = " ".join(
        str(row[3])
        for row in store.connection.execute(
            "EXPLAIN QUERY PLAN SELECT seq, kind, refs_json FROM research_event WHERE research_id=? ORDER BY seq LIMIT 50",
            ("r-idx",),
        ).fetchall()
    )
    assert "INDEX" in plan.upper()
