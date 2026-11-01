"""PR2: round commit, budgets, and restart recovery."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import replace
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd
import pytest

from engine.export import build_research_record_pack, build_strategy_pack, strategy_pack_eligibility
from engine.main import ResearchCommandService, advance_running_research
from engine.metrics import SimulationReport
from engine.research.clock import TimeBudget
from engine.research.effective_spec import inherited_drawdown_floor
from engine.research.evidence_window import authorize_evidence_split, evidence_grade
from engine.research.frozen_input import ensure_frozen_version_input
from engine.research.gather import PapersAdapter, SecEdgarAdapter
from engine.research.loop import ResearchLoop
from engine.research.market_calendar import align_asset_calendar
from engine.research.materials_store import read_material_text, write_immutable_material
from engine.research.models import (
    AssetClass,
    ConfirmKind,
    ConfirmRequest,
    CoverageFloor,
    Market,
    ResearchEvent,
    ResearchStatus,
    Slot,
    Universe,
    new_research,
)
from engine.research.recovery_harness import seed_running
from engine.research.round_store import RoundDecision, RoundReplay, guarded_billed_call
from engine.research.runtime import EnginePaths
from engine.research.simulate import simulate_daily
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.research.symbol_pool import SymbolPool, pool_final_grade, pool_for_market
from engine.research.universe_validation import ensure_runnable_universe, refresh_symbol_probe
from engine.research.user_errors import UserFacingError
from engine.strategy import MeanReversionStrategy, StrategySpec
from engine.verifiers import run_verifiers
from tests.test_export_pack import completed_research, snapshot
from tests.test_loop_runtime import NOW, FakeBuilder, FakeMonotonic, PassReviewer, running_research

PIN_START = date(2014, 1, 2)
PIN_END = date(2016, 12, 30)


def _spawn(database: Path, research_id: str, *, barrier: str = "", extra: dict[str, str] | None = None) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["ALPHALOOP_RECOVERY_DB"] = str(database)
    env["ALPHALOOP_RECOVERY_ID"] = research_id
    if barrier:
        env["ALPHALOOP_CRASH_BARRIER"] = barrier
    else:
        env.pop("ALPHALOOP_CRASH_BARRIER", None)
    if extra:
        env.update(extra)
    return subprocess.Popen(
        [sys.executable, "-m", "engine.research.recovery_harness"],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _kill_at_barrier(database: Path, research_id: str, barrier: str, *, extra: dict[str, str] | None = None) -> str:
    """Kill is SIGKILL on POSIX and TerminateProcess on Windows."""
    proc = _spawn(database, research_id, barrier=barrier, extra=extra)
    assert proc.stdout is not None
    output: list[str] = []
    deadline = time.monotonic() + 30
    ready = False
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if line:
            output.append(line)
            if f"ALPHALOOP_BARRIER_READY {barrier}" in line:
                ready = True
                break
        elif proc.poll() is not None:
            break
    assert ready, "".join(output)
    proc.kill()
    proc.wait(timeout=5)
    return "".join(output)


def _resume(database: Path, research_id: str, *, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    proc = _spawn(database, research_id, extra=extra)
    assert proc.stdout is not None
    output, _ = proc.communicate(timeout=30)
    return subprocess.CompletedProcess(proc.args, proc.returncode, output, "")


def _loop(store: SQLiteStore, builder: FakeBuilder | None = None) -> ResearchLoop:
    return ResearchLoop(
        store,
        builder or FakeBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    )


def test_crash_barriers_resume_one_round(tmp_path: Path) -> None:
    for barrier in ("after_freeze", "after_review", "after_round_commit"):
        database = tmp_path / f"{barrier}.db"
        counter = tmp_path / f"{barrier}.count"
        counter.write_text("0", encoding="utf-8")
        research_id = f"r-{barrier}"
        store = SQLiteStore(database)
        seed_running(store, research_id, NOW)
        extra = {"ALPHALOOP_LOAD_COUNTER": str(counter)}
        _kill_at_barrier(database, research_id, barrier, extra=extra)
        loads_after_kill = int(counter.read_text(encoding="utf-8"))
        resumed = _resume(database, research_id, extra=extra)
        assert resumed.returncode == 0, resumed.stdout
        reopened = SQLiteStore(database)
        research = reopened.load(research_id)
        rounds = [item for version in research.versions for item in version.rounds]
        assert len(rounds) == 1
        assert rounds[0].round_id == "v1-r1"
        receipt = reopened.round_receipt(research_id, 1, 1)
        assert receipt is not None
        assert receipt["round_id"] == "v1-r1"
        assert receipt["csv_fingerprint"]
        assert receipt["window_m"] == 1
        assert reopened.window_round_count(
            f"pool-v1|yahoo_daily|{PIN_START.isoformat()}|{PIN_END.isoformat()}"
        ) == 1
        assert int(counter.read_text(encoding="utf-8")) == loads_after_kill or barrier == "after_freeze"
        if barrier != "after_freeze":
            assert int(counter.read_text(encoding="utf-8")) == loads_after_kill
        again = _resume(database, research_id, extra=extra)
        assert again.returncode == 0, again.stdout
        final = SQLiteStore(database).load(research_id)
        assert len([item for version in final.versions for item in version.rounds]) == 1
        assert SQLiteStore(database).window_round_count(
            f"pool-v1|yahoo_daily|{PIN_START.isoformat()}|{PIN_END.isoformat()}"
        ) == 1


def test_duplicate_tick_commits_one_round(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "dup.db")
    store.create(running_research())
    gate = threading.Barrier(2)

    class Both(FakeBuilder):
        def build(self, research, attempt_number: int):
            gate.wait(timeout=5)
            return super().build(research, attempt_number)

    loop = _loop(store, Both())
    errors: list[BaseException] = []

    def run() -> None:
        try:
            loop.run_once("r-loop")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert errors == []
    assert not any(thread.is_alive() for thread in threads)
    loaded = store.load("r-loop")
    assert len(loaded.versions[0].rounds) == 1
    rows = store.connection.execute(
        "SELECT COUNT(*) FROM committed_round WHERE research_id=?",
        ("r-loop",),
    ).fetchone()
    assert int(rows[0]) == 1


def test_corrupt_or_missing_frozen_input_does_not_refetch(tmp_path: Path) -> None:
    class Port:
        def __init__(self) -> None:
            self.loads = 0

        def load_daily(self, symbols, start, end):
            self.loads += 1
            index = pd.bdate_range(PIN_START, periods=5)
            if symbols == ("SPX",):
                return pd.DataFrame({"SPX": [1, 2, 3, 4, 5]}, index=index)
            return pd.DataFrame({symbol: [1, 2, 3, 4, 5] for symbol in symbols}, index=index)

    research = replace(
        running_research(),
        brief=replace(
            running_research().brief,
            thesis=Slot("mean reversion", True),
            universe=Slot(Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA",)), True),
        ),
        data_window_start=PIN_START,
        data_window_end=PIN_END,
    )
    port = Port()
    root = tmp_path / "snapshots"
    first = ensure_frozen_version_input(
        snapshot_root=root,
        research=research,
        version_number=1,
        symbols=("AAA",),
        start=PIN_START,
        end=PIN_END,
        thesis="mean reversion",
        material_ports=(),
        live_port=port,
    )
    assert first.prices.shape[0] == 5
    loads = port.loads
    from engine.research.frozen_input import frozen_input_path

    path = frozen_input_path(root, research.research_id, 1)
    path.write_bytes(b"not a pickle")
    with pytest.raises(UserFacingError) as caught:
        ensure_frozen_version_input(
            snapshot_root=root,
            research=research,
            version_number=1,
            symbols=("AAA",),
            start=PIN_START,
            end=PIN_END,
            thesis="mean reversion",
            material_ports=(),
            live_port=port,
        )
    assert caught.value.code == "FROZEN_INPUT_UNREADABLE"
    assert port.loads == loads
    path.unlink()
    with pytest.raises(UserFacingError):
        ensure_frozen_version_input(
            snapshot_root=root,
            research=research,
            version_number=1,
            symbols=("AAA",),
            start=PIN_START,
            end=PIN_END,
            thesis="mean reversion",
            material_ports=(),
            live_port=port,
        )
    assert port.loads == loads


def test_database_busy_retries_then_pauses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SQLiteStore(tmp_path / "busy.db")
    store.create(running_research())
    monkeypatch.setenv("ALPHALOOP_INJECT_DB_BUSY", "once")
    done = _loop(store).run_once("r-loop")
    assert done.status is ResearchStatus.COMPLETED
    assert len(done.versions[0].rounds) == 1

    store_b = SQLiteStore(tmp_path / "busy-always.db")
    store_b.create(running_research())
    monkeypatch.setenv("ALPHALOOP_INJECT_DB_BUSY", "always")
    paused = _loop(store_b).run_once("r-loop")
    assert paused.status is ResearchStatus.PAUSED
    assert paused.last_run_error_code == "DB_BUSY"
    assert paused.versions[0].rounds == ()


def test_pause_during_round_discards_the_worker_result(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "pause.db")
    store.create(running_research())

    class Pausing(FakeBuilder):
        def build(self, research, attempt_number: int):
            current = store.load(research.research_id)
            paused = transition(current, ResearchEvent.PAUSE, NOW.replace(second=1))
            store.save(paused, current.updated_at)
            return super().build(research, attempt_number)

    result = _loop(store, Pausing()).run_once("r-loop")
    assert result.status is ResearchStatus.PAUSED
    assert result.versions[0].rounds == ()
    assert store.load("r-loop").status is ResearchStatus.PAUSED


def test_effective_slices_lose_at_most_one_heartbeat(tmp_path: Path) -> None:
    mono = FakeMonotonic()
    store = SQLiteStore(tmp_path / "time.db")
    store.create(running_research())
    budget = TimeBudget(mono)
    budget.begin(ResearchStatus.RUNNING, "r-loop")
    mono.value += 12
    tail = budget.checkpoint("r-loop", store)
    assert tail == pytest.approx(2)
    assert store.effective_seconds_ledger("r-loop") == pytest.approx(10)
    reopened = SQLiteStore(tmp_path / "time.db")
    restored = ResearchLoop(
        reopened,
        FakeBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 0.0),
        lambda: NOW,
    )._reconcile_time(reopened.load("r-loop"))
    assert restored.effective_seconds == pytest.approx(10)


def test_queued_research_does_not_borrow_budget_or_the_worker(tmp_path: Path) -> None:
    mono = FakeMonotonic()
    budget = TimeBudget(mono)
    first = replace(running_research(), research_id="r-a")
    second = replace(running_research(), research_id="r-b", effective_seconds=1.0)
    budget.begin(ResearchStatus.RUNNING, "r-a")
    mono.value += 30
    budget.begin(ResearchStatus.RUNNING, "r-b")
    mono.value += 4
    assert budget.finish(second).effective_seconds == pytest.approx(5)
    assert budget.finish(first).effective_seconds == pytest.approx(34)

    store = SQLiteStore(tmp_path / "lease.db")
    store.create(first)
    store.create(second)
    assert store.try_acquire_worker("r-a") is True
    advance_running_research(store, _loop(store), "r-b")
    assert store.load("r-b").versions[0].rounds == ()
    assert store.load("r-b").effective_seconds == pytest.approx(1)
    store.release_worker("r-a")
    advance_running_research(store, _loop(store), "r-b")
    assert len(store.load("r-b").versions[0].rounds) == 1


def test_same_material_doi_keeps_both_texts(tmp_path: Path) -> None:
    from engine.research.gather import Material

    root = tmp_path / "materials"
    first = Material(
        "doi:10.1000/example",
        "papers",
        "One",
        "https://doi.org/10.1000/example",
        "version one text",
        NOW,
        published_at=date(2020, 1, 1),
        published_precision="day",
    )
    second = replace(first, text="version two text", title="Two")
    path_v1 = write_immutable_material(root, first)
    path_v2 = write_immutable_material(root, second)
    assert path_v1 != path_v2
    assert read_material_text(path_v1) == "version one text"
    assert read_material_text(path_v2) == "version two text"
    assert write_immutable_material(root, first) == path_v1


def test_step_run_key_is_unique_and_billed_unknown_is_not_resent(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "steps.db")
    store.create(running_research())
    first = store.claim_step("r-loop", 1, 1, 1, "simulate", "hash-a")
    second = store.claim_step("r-loop", 1, 1, 1, "simulate", "hash-a")
    assert first[0] == "pending"
    assert second[0] == "pending"
    assert len(store.step_rows("r-loop")) == 1
    store.complete_step("r-loop", 1, 1, 1, "simulate", "hash-a", "csv")
    assert store.claim_step("r-loop", 1, 1, 1, "simulate", "hash-a") == ("done", "csv")

    calls = {"n": 0}

    def send() -> str:
        calls["n"] += 1
        return "ok"

    assert guarded_billed_call(
        store,
        research_id="r-loop",
        version=1,
        round_number=1,
        attempt=1,
        step="review",
        input_hash="paid",
        call=send,
    ) == "ok"
    assert calls["n"] == 1
    store.mark_step_unknown("r-loop", 1, 1, 1, "review", "paid")
    with pytest.raises(UserFacingError) as caught:
        guarded_billed_call(
            store,
            research_id="r-loop",
            version=1,
            round_number=1,
            attempt=1,
            step="review",
            input_hash="paid",
            call=send,
        )
    assert caught.value.code == "REMOTE_UNKNOWN_NEEDS_AUTH"
    assert calls["n"] == 1
    assert store.billed_budget("r-loop") >= 1
    guarded_billed_call(
        store,
        research_id="r-loop",
        version=1,
        round_number=1,
        attempt=1,
        step="review",
        input_hash="paid",
        call=send,
        authorize=True,
    )
    assert calls["n"] == 2


def test_billed_sidecar_kill_does_not_resend(tmp_path: Path, allow_loopback_sockets: None) -> None:
    received: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            received.append(self.path)
            time.sleep(30)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    database = tmp_path / "billed.db"
    store = SQLiteStore(database)
    store.create(replace(running_research(), research_id="r-bill"))
    url = f"http://127.0.0.1:{server.server_port}/review"
    proc = _spawn(
        database,
        "r-bill",
        extra={"ALPHALOOP_RECOVERY_MODE": "billed", "ALPHALOOP_FAKE_URL": url},
    )
    deadline = time.monotonic() + 20
    while not received and time.monotonic() < deadline:
        time.sleep(0.05)
    assert received, "fake service did not see the billed request"
    proc.kill()
    proc.wait(timeout=5)
    restarted = SQLiteStore(database)
    assert restarted.billed_budget("r-bill") >= 1
    with pytest.raises(UserFacingError):
        guarded_billed_call(
            restarted,
            research_id="r-bill",
            version=1,
            round_number=1,
            attempt=1,
            step="review",
            input_hash="billed-key",
            call=lambda: received.append("resent"),
        )
    assert received == ["/review"]
    server.shutdown()


def test_create_without_research_id_replays_the_stored_row(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "create.db")
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    created = service.handle(
        {"type": "create_draft", "research_id": "r-create", "command_id": "c-create"}
    )
    assert created["research_id"] == "r-create"
    with store.connection:
        store.connection.execute("DELETE FROM command_receipt")
    replayed = service.handle({"type": "create_draft", "command_id": "c-create"})
    assert replayed["research_id"] == "r-create"
    assert [item.research_id for item in store.list_research()] == ["r-create"]
    assert service.journal._receipt("r-create", "c-create") is not None


def test_running_ids_do_not_decode_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SQLiteStore(tmp_path / "wide.db")
    now = NOW.isoformat()
    with store.connection:
        for index in range(100):
            status = "running" if index % 2 == 0 else "draft"
            store.connection.execute(
                """
                INSERT INTO researches(
                    research_id, state_json, updated_at, status, revision, last_seq
                ) VALUES(?,?,?,?,0,0)
                """,
                (f"r-{index:03d}", json.dumps({"status": status}), now, status),
            )
        store.connection.executemany(
            """
            INSERT INTO research_event(
                research_id, seq, version, kind, refs_json, created_at
            ) VALUES(?,?,?,?,?,?)
            """,
            [
                (f"r-{index:03d}", seq, None, "note", "{}", now)
                for index in range(100)
                for seq in range(1, 1001)
            ],
        )
    import engine.research.store as store_module

    calls = {"n": 0}
    original = store_module.json.loads

    def counting(payload: str, *args: object, **kwargs: object):
        calls["n"] += 1
        return original(payload, *args, **kwargs)

    monkeypatch.setattr(store_module.json, "loads", counting)
    samples = []
    for _ in range(20):
        started = time.perf_counter()
        ids = store.running_ids()
        heads = store.list_heads()
        store.heartbeat(
            __import__("engine.research.runtime", fromlist=["OwnerRecord"]).OwnerRecord(
                "desktop",
                1,
                "ready",
            ),
            NOW,
        )
        samples.append(time.perf_counter() - started)
        assert len(ids) == 50
        assert len(heads) == 100
    assert calls["n"] == 0
    samples.sort()
    assert samples[int(0.95 * (len(samples) - 1))] < 0.25
    plan = store.connection.execute(
        "EXPLAIN QUERY PLAN SELECT research_id FROM researches WHERE status='running'"
    ).fetchall()
    assert any("idx_researches_status" in " ".join(str(part) for part in row) for row in plan)


def test_asset_calendar_is_shared_by_simulate_reverify_and_pack(tmp_path: Path) -> None:
    index = pd.bdate_range("2024-01-02", periods=32)
    asset_values = [100.0] * 30 + [100.0, 121.0]
    bench_values = [100.0] * 30 + [110.0, 121.0]
    # Drop the asset's middle session of the last three dates: index[-2] is benchmark-only.
    asset = pd.DataFrame({"AAA": asset_values}, index=index).drop(index[-2])
    benchmark = pd.Series(bench_values, index=index, name="SPX")
    _aligned_prices, aligned_bench = align_asset_calendar(asset, benchmark)
    assert aligned_bench.iloc[-1] / aligned_bench.iloc[-2] - 1 == pytest.approx(0.21)

    class Port:
        def load_daily(self, symbols, start, end):
            if symbols == ("SPX",):
                return benchmark.to_frame()
            return asset

    spec = StrategySpec(
        id="calendar",
        thesis_locked="mean reversion",
        universe=Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA",)),
        frequency="1d",
        side="long_only",
        method_set=(),
        model_family="mean_reversion",
        lookback_days=2,
        entry_z=0.5,
    )
    snapshot_path = tmp_path / "snap.csv"
    report = simulate_daily(
        MeanReversionStrategy(spec),
        Port(),
        index[0].date(),
        index[-1].date(),
        snapshot_path=snapshot_path,
    )
    frozen = pd.read_csv(snapshot_path, index_col="date", parse_dates=True)
    assert 110.0 not in set(frozen["__benchmark__"].tolist())
    assert frozen["__benchmark__"].iloc[-1] / frozen["__benchmark__"].iloc[-2] - 1 == pytest.approx(0.21)

    class FrozenPort:
        def load_daily(self, symbols, start, end):
            if symbols == ("SPX",):
                return frozen[["__benchmark__"]].rename(columns={"__benchmark__": "SPX"})
            return frozen[list(symbols)]

    reverified = simulate_daily(
        MeanReversionStrategy(spec),
        FrozenPort(),
        frozen.index.min().date(),
        frozen.index.max().date(),
    )
    assert reverified.r_bench_ann == pytest.approx(report.r_bench_ann)
    assert reverified.excess_ann == pytest.approx(report.excess_ann)

    panel_prices = asset.copy()
    panel = snapshot()
    from engine.strategy import MarketPanel

    gapped = MarketPanel(panel_prices, NOW, benchmark)
    research = replace(completed_research(), research_id="r-cal")
    # Give the completed round this spec so the pack runner uses lookback 2.
    attempt = research.versions[-1].rounds[-1].accepted_attempt
    research = replace(
        research,
        versions=(
            replace(
                research.versions[-1],
                rounds=(
                    replace(
                        research.versions[-1].rounds[-1],
                        accepted_attempt=replace(attempt, spec=spec, simulation=report),
                    ),
                ),
            ),
        ),
    )
    archive = build_strategy_pack(research, MeanReversionStrategy(spec), gapped, tmp_path / "pack.zip")
    import zipfile

    with zipfile.ZipFile(archive) as bundle:
        bench_csv = pd.read_csv(bundle.open("data/benchmark.csv"), index_col="date")
    assert bench_csv["benchmark"].iloc[-1] / bench_csv["benchmark"].iloc[-2] - 1 == pytest.approx(0.21)
    root = tmp_path / "unpacked"
    root.mkdir()
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(root)
    ran = subprocess.run(
        [sys.executable, "run_backtest.py"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    packed = json.loads(ran.stdout)
    assert packed["r_bench_ann"] == pytest.approx(report.r_bench_ann)
    del panel


def test_version_inherits_drawdown_floor_across_restart(tmp_path: Path) -> None:
    research = new_research("r-floor", NOW)
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA",))
    research = replace(
        research,
        brief=replace(
            research.brief,
            thesis=Slot("mean reversion", True),
            universe=Slot(universe, True),
            max_effective_hours=Slot(6.0, True),
            round1_methods=Slot((), True),
            coverage_floor=Slot(CoverageFloor(1, 1, 50.0), True),
        ),
    )
    opened = transition(research, ResearchEvent.CONFIRM_RUN, NOW)
    assert opened.versions[0].effective_spec_snapshot is not None
    assert opened.versions[0].effective_spec_snapshot["max_drawdown_floor"] == -0.25
    waiting = replace(
        opened,
        status=ResearchStatus.AWAITING_CONFIRM,
        pending_confirm=ConfirmRequest(
            request_id="floor",
            kind=ConfirmKind.ECONOMIC,
            proposed_change="max_drawdown_floor",
            reason="tighten",
            effect="new version",
            patch=(("max_drawdown_floor", -0.10),),
            why_change=(),
            created_at=NOW,
        ),
    )
    # Economic approval validates evidence. Use a non-evidence change class via coverage-like
    # patch on an economic request only when why_change is empty — CONFIRM_APPROVE requires
    # evidence for ECONOMIC. Drive inheritance through MODIFY by seeding the snapshot.
    tightened = replace(
        opened,
        versions=(
            replace(
                opened.versions[0],
                effective_spec_snapshot={
                    **(opened.versions[0].effective_spec_snapshot or {}),
                    "max_drawdown_floor": -0.10,
                },
            ),
        ),
        status=ResearchStatus.PAUSED,
        pending_confirm=ConfirmRequest(
            request_id="hours",
            kind=ConfirmKind.ECONOMIC,
            proposed_change="hours",
            reason="extend",
            effect="new version",
            patch=(("max_effective_hours", 8.0),),
        ),
    )
    extended = transition(tightened, ResearchEvent.MODIFY_CONFIRM, NOW)
    assert len(extended.versions) == 2
    assert extended.versions[1].effective_spec_snapshot is not None
    assert extended.versions[1].effective_spec_snapshot["max_drawdown_floor"] == -0.10
    assert extended.versions[1].parent_digest
    assert inherited_drawdown_floor(extended, None) == -0.10
    rejected = transition(waiting, ResearchEvent.CONFIRM_REJECT, NOW)
    assert len(rejected.versions) == 1
    store = SQLiteStore(tmp_path / "floor.db")
    store.create(research)
    store.save(extended, research.updated_at)
    loaded = SQLiteStore(tmp_path / "floor.db").load("r-floor")
    spec = StrategySpec(
        id="floor",
        thesis_locked="mean reversion",
        universe=universe,
        frequency="1d",
        side="long_only",
        method_set=(),
        model_family="mean_reversion",
        lookback_days=20,
        entry_z=1.0,
        max_drawdown_floor=inherited_drawdown_floor(loaded, None),
    )
    report = replace(snapshot_report(), max_drawdown=-0.18, sharpe_oos=0.2, excess_ann=0.01)
    verification = run_verifiers(report, spec)
    scorecard = next(item for item in verification.results if item.verifier_id == "scorecard.market")
    assert scorecard.passed is False


def snapshot_report() -> SimulationReport:
    from tests.test_loop_runtime import simulation

    return simulation()


def test_probe_stays_inside_the_explore_window(tmp_path: Path) -> None:
    explore_end = date(2024, 6, 1)
    holdout_end = date(2024, 12, 31)
    seen: list[date] = []

    class Port:
        def load_daily(self, symbols, start, end):
            seen.append(end)
            index = pd.bdate_range(start, end)
            data = {}
            for symbol in symbols:
                if symbol == "LATE" and end > explore_end:
                    data[symbol] = [10.0] * len(index)
                elif symbol == "LATE":
                    data[symbol] = [float("nan")] * len(index)
                else:
                    data[symbol] = [10.0 + i for i in range(len(index))]
            return pd.DataFrame(data, index=index)

    from engine.research.pool_data_shrink import set_pool_data_loader

    set_pool_data_loader(Port())
    base = replace(
        new_research("r-probe", NOW),
        brief=replace(
            new_research("r-probe", NOW).brief,
            thesis=Slot("mean reversion", True),
            universe=Slot(
                Universe(
                    Market.US,
                    AssetClass.EQUITY,
                    AssetClass.EQUITY,
                    ("AAA", "LATE"),
                    user_symbols_override=True,
                ),
                True,
            ),
            max_effective_hours=Slot(6.0, True),
            round1_methods=Slot((), True),
            coverage_floor=Slot(CoverageFloor(1, 1, 80.0), True),
        ),
    )
    static = authorize_evidence_split(
        base,
        explore_end=explore_end,
        holdout_start=date(2024, 6, 2),
        holdout_end=holdout_end,
    )
    static = replace(static, evidence_policy=replace(static.evidence_policy, explore_end=None))  # type: ignore[arg-type]
    assert refresh_symbol_probe(static) == static
    assert seen == []
    authorized = authorize_evidence_split(
        base,
        explore_end=explore_end,
        holdout_start=date(2024, 6, 2),
        holdout_end=holdout_end,
    )
    probed = refresh_symbol_probe(authorized)
    pinned = ensure_runnable_universe(probed)
    assert seen
    assert max(seen) <= explore_end
    assert pinned.data_window_end == explore_end
    set_pool_data_loader(None)


def test_pool_as_of_blocks_late_and_undated_lists_from_strategy_packs(tmp_path: Path) -> None:
    as_of = date(2024, 1, 1)
    known = _pool("known", "2023-12-01")
    late = _pool("late", "2024-06-01")
    unknown = _pool("unknown", None)
    chosen = pool_for_market(
        Market.US,
        AssetClass.EQUITY,
        AssetClass.EQUITY,
        as_of=as_of,
        pools=(late, unknown, known),
    )
    assert chosen is not None and chosen.version_id == "known"
    assert pool_final_grade(late, as_of)[0] == "exploratory"
    assert pool_final_grade(unknown, as_of)[0] == "exploratory"
    assert pool_for_market(
        Market.US,
        AssetClass.EQUITY,
        AssetClass.EQUITY,
        as_of=as_of,
        pools=(late, unknown),
    ) is None

    research = replace(
        completed_research(),
        symbol_list_version="late",
        evidence_policy=authorize_evidence_split(
            completed_research(),
            explore_end=as_of,
            holdout_start=date(2024, 1, 2),
            holdout_end=date(2024, 6, 1),
            mode="final",
        ).evidence_policy,
    )
    monkey = pytest.MonkeyPatch()
    monkey.setattr(
        "engine.research.evidence_window.pool_by_version",
        lambda version_id: late if version_id == "late" else None,
    )
    grade, reason = evidence_grade(research)
    assert grade == "exploratory"
    assert reason
    eligibility = strategy_pack_eligibility(research)
    assert "evidence_grade" in eligibility.failed_checks
    assert eligibility.eligible is False
    with pytest.raises(ValueError):
        build_strategy_pack(research, MeanReversionStrategy(research.versions[-1].rounds[-1].accepted_attempt.spec), snapshot(), tmp_path / "no.zip")
    record = build_research_record_pack(research, tmp_path / "record.zip")
    import zipfile

    with zipfile.ZipFile(record) as bundle:
        history = json.loads(bundle.read("history/research.json"))
    assert history["evidence_grade"]["grade"] == "exploratory"
    monkey.undo()


def _pool(version_id: str, available: str | None) -> SymbolPool:
    return SymbolPool(
        version_id=version_id,
        display_name=version_id,
        generated_date="2024-06-01",
        market=Market.US,
        asset_class=AssetClass.EQUITY,
        underlying_asset_class=AssetClass.EQUITY,
        symbols=("AAA",),
        actual_available_at=available,
        source_fingerprint="abc",
    )


def test_public_query_drops_local_sentinels(tmp_path: Path) -> None:
    sentinel = "HOLDINGS-SECRET /tmp/alpha-private-path"
    thesis = f"{sentinel} mean reversion"

    class Client:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []
            self.error: Exception | None = None

        def get(self, url: str, **kwargs: object):
            self.calls.append({"url": url, "params": kwargs.get("params"), "headers": kwargs.get("headers")})
            if self.error is not None:
                raise self.error
            response = type("Response", (), {})()
            response.raise_for_status = lambda: None
            response.json = lambda: {"message": {"items": []}} if "crossref" in url else {}
            return response

    client = Client()
    papers = PapersAdapter(client, lambda: NOW)  # type: ignore[arg-type]
    assert papers.fetch(thesis) == ()
    assert client.calls
    blob = json.dumps(client.calls)
    assert sentinel not in blob
    assert "mean reversion" in blob
    client.error = RuntimeError(sentinel)
    assert papers.fetch(thesis) == ()
    assert sentinel not in " ".join(papers.fetch_errors)
    sec = SecEdgarAdapter(client, lambda: NOW, "alphaloop test")  # type: ignore[arg-type]
    client.error = RuntimeError(sentinel)
    assert sec.fetch(thesis) == ()
    assert sentinel not in " ".join(sec.fetch_errors)
    client.error = None
    client.calls.clear()
    assert papers.fetch(sentinel) == ()
    assert client.calls == []


def test_round_decision_replay_does_not_double_count_m(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "replay.db")
    store.create(running_research())
    done = _loop(store).run_once("r-loop")
    decision = RoundDecision(
        kind="round_committed",
        round_id=done.versions[0].rounds[0].round_id,
        attempt_id=done.versions[0].rounds[0].accepted_attempt.attempt_id,
        version_number=1,
        round_number=1,
        candidate_hash="same-candidate",
    )
    with pytest.raises(RoundReplay):
        store.commit_round_decision(
            done,
            expected_updated_at=done.updated_at,
            expected_revision=store.revision_of("r-loop"),
            decision=decision,
        )
    assert len(store.load("r-loop").versions[0].rounds) == 1
