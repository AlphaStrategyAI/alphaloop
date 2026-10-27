"""HTTP API must stay responsive while market-data probes run or hang."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from engine.main import ResearchCommandService, start_api
from engine.research.data_availability import TRANSIENT_DATA_CODE
from engine.research.models import AssetClass, Market, ResearchStatus, Slot, Universe, new_research
from engine.research.pool_data_shrink import set_pool_data_loader
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError
from tests.test_state_machine import locked_brief

NOW = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)

pytestmark = pytest.mark.usefixtures("allow_loopback_sockets")


class _GateLoader:
    """Offline bars. Blocks inside the first load so a second confirm overlaps it."""

    def __init__(self) -> None:
        self.calls = 0
        self.entered = threading.Event()
        self.release = threading.Event()

    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        self.calls += 1
        self.entered.set()
        assert self.release.wait(timeout=5.0)
        index = pd.to_datetime([start, end])
        return pd.DataFrame(
            {symbol: pd.Series([100.0, 101.0], index=index, name=symbol) for symbol in symbols}
        )


class _SlowLoader:
    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        from engine.research import market_data_timeouts as mdt

        time.sleep(mdt.MARKET_DATA_LOAD_TIMEOUT_SEC + 5.0)
        return pd.DataFrame()


def _confirm_ready_in_store(store: SQLiteStore) -> None:
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
    research = replace(new_research("r-http", NOW), brief=brief)
    store.create(research)


def _post(endpoint: str, token: str, body: dict) -> tuple[int, dict]:
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{endpoint}/commands",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def test_threading_server_list_responds_while_confirm_blocks_on_market_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from engine.research import market_data_timeouts as mdt

    monkeypatch.setattr(mdt, "MARKET_DATA_LOAD_TIMEOUT_SEC", 0.5)

    set_pool_data_loader(_SlowLoader())
    store = SQLiteStore(tmp_path / "http.db")
    _confirm_ready_in_store(store)
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    token = "test-token"
    server, endpoint = start_api(service, token)

    confirm_error: dict | None = None

    def run_confirm() -> None:
        nonlocal confirm_error
        confirm_error = dict(
            zip(
                ("status", "body"),
                _post(
                    endpoint,
                    token,
                    {
                        "type": "confirm_run",
                        "research_id": "r-http",
                        "data_source_id": "yahoo_daily",
                        "unlicensed_acknowledged": True,
                    },
                ),
                strict=True,
            )
        )

    thread = threading.Thread(target=run_confirm, name="confirm-run")
    thread.start()
    time.sleep(0.05)
    started = time.monotonic()
    status, body = _post(
        endpoint,
        token,
        {"type": "fetch_view", "route": "#/research"},
    )
    elapsed = time.monotonic() - started
    thread.join(timeout=5.0)

    server.shutdown()
    set_pool_data_loader(None)

    assert status == 200
    assert body["kind"] == "research_list"
    assert elapsed < 2.0, f"list fetch blocked for {elapsed:.1f}s"
    assert confirm_error is not None
    assert confirm_error["status"] == 400
    assert confirm_error["body"]["code"] == "MARKET_DATA_TIMEOUT"


def test_progress_stays_visible_while_confirm_holds_the_research(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from engine.research import market_data_timeouts as mdt
    from engine.research.market_data_progress import (
        clear_market_data_progress,
        set_market_data_progress,
    )

    monkeypatch.setattr(mdt, "MARKET_DATA_LOAD_TIMEOUT_SEC", 2.0)

    class _ProgressLoader:
        def load_daily(
            self,
            symbols: tuple[str, ...],
            start: date,
            end: date,
        ) -> pd.DataFrame:
            set_market_data_progress(4, 503, "yahoo")
            time.sleep(0.5)
            clear_market_data_progress()
            index = pd.to_datetime([start, end])
            return pd.DataFrame(
                {symbol: pd.Series([100.0, 101.0], index=index) for symbol in symbols}
            )

    set_pool_data_loader(_ProgressLoader())
    store = SQLiteStore(tmp_path / "progress.db")
    _confirm_ready_in_store(store)
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    token = "test-token"
    server, endpoint = start_api(service, token)
    thread = threading.Thread(
        target=lambda: _post(
            endpoint,
            token,
            {
                "type": "confirm_run",
                "research_id": "r-http",
                "data_source_id": "yahoo_daily",
                "unlicensed_acknowledged": True,
            },
        ),
        name="confirm-progress",
    )
    thread.start()
    status = 0
    body: dict = {}
    view_status = 0
    view: dict = {}
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        status, body = _post(endpoint, token, {"type": "market_data_progress"})
        view_status, view = _post(
            endpoint,
            token,
            {"type": "fetch_view", "route": "#/research/r-http"},
        )
        if body.get("marketDataProgress") and view.get("marketDataProgress"):
            break
        time.sleep(0.02)
    thread.join(timeout=5.0)
    server.shutdown()
    set_pool_data_loader(None)

    assert status == 200
    assert body["marketDataProgress"] == {"done": 4, "total": 503, "source": "yahoo"}
    assert body["hostStatus"] == "running"
    assert view_status == 200
    assert view["marketDataProgress"]["done"] == 4
    assert view["marketDataProgress"]["total"] == 503


def test_confirm_run_transient_within_market_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from engine.research import market_data_timeouts as mdt

    monkeypatch.setattr(mdt, "MARKET_DATA_LOAD_TIMEOUT_SEC", 0.5)

    set_pool_data_loader(_SlowLoader())
    store = SQLiteStore(tmp_path / "deadline.db")
    _confirm_ready_in_store(store)
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))

    started = time.monotonic()
    with pytest.raises(UserFacingError) as exc:
        service.handle(
            {
                "type": "confirm_run",
                "research_id": "r-http",
                "data_source_id": "yahoo_daily",
                "unlicensed_acknowledged": True,
            }
        )
    elapsed = time.monotonic() - started
    set_pool_data_loader(None)

    assert exc.value.code == "MARKET_DATA_TIMEOUT"
    assert "MARKET_DATA_TIMEOUT" in exc.value.message
    assert elapsed < mdt.MARKET_DATA_LOAD_TIMEOUT_SEC + 2.0
    saved = store.load("r-http")
    assert saved.status is ResearchStatus.DRAFT
    assert saved.last_run_error_code is None
    view = service.view_for("#/research/r-http")
    assert view["kind"] == "confirm_run"
    assert "MARKET_DATA_TIMEOUT" in view["confirmDataNotice"]


def test_set_price_source_during_confirm_probe_does_not_concurrent_write(tmp_path: Path) -> None:
    """Acking Yahoo while confirm_run is inside the market probe must not lose the run.

    The card fires set_price_source and confirm_run back to back. confirm_run
    holds the research across the probe; the source save used to bump
    updated_at underneath that snapshot and the run died with ConcurrentWrite.
    """
    loader = _GateLoader()
    set_pool_data_loader(loader)
    store = SQLiteStore(tmp_path / "source-race.db")
    _confirm_ready_in_store(store)
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    server, endpoint = start_api(service, "test-token")
    confirm_box: dict[str, tuple[int, dict]] = {}
    source_box: dict[str, tuple[int, dict]] = {}
    errors: list[BaseException] = []

    def run_confirm() -> None:
        try:
            confirm_box["pair"] = _post(
                endpoint,
                "test-token",
                {
                    "type": "confirm_run",
                    "research_id": "r-http",
                    "data_source_id": "yahoo_daily",
                    "unlicensed_acknowledged": True,
                },
            )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    def run_source() -> None:
        try:
            assert loader.entered.wait(timeout=2.0)
            source_box["pair"] = _post(
                endpoint,
                "test-token",
                {
                    "type": "set_price_source",
                    "research_id": "r-http",
                    "data_source_id": "yahoo_daily",
                    "unlicensed_acknowledged": True,
                },
            )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    try:
        confirm = threading.Thread(target=run_confirm, name="confirm-run")
        source = threading.Thread(target=run_source, name="set-price-source")
        confirm.start()
        assert loader.entered.wait(timeout=2.0)
        source.start()
        time.sleep(0.05)
        loader.release.set()
        confirm.join(timeout=5.0)
        source.join(timeout=5.0)
        assert not confirm.is_alive()
        assert not source.is_alive()
        assert errors == []
        confirm_status, confirm_body = confirm_box["pair"]
        source_status, source_body = source_box["pair"]
        assert confirm_status == 200, confirm_body
        assert confirm_body.get("code") != "internal_error"
        assert "ConcurrentWrite" not in json.dumps(confirm_body)
        assert confirm_body["status"] == "running"
        assert source_status == 200, source_body
        assert source_body.get("code") != "internal_error"
        assert "ConcurrentWrite" not in json.dumps(source_body)
        loaded = store.load("r-http")
        assert loaded.status is ResearchStatus.RUNNING
        assert loaded.data_source_id == "yahoo_daily"
    finally:
        loader.release.set()
        server.shutdown()
        set_pool_data_loader(None)


def test_overlapping_confirm_run_returns_success_and_starts_once(tmp_path: Path) -> None:
    loader = _GateLoader()
    set_pool_data_loader(loader)
    store = SQLiteStore(tmp_path / "overlap.db")
    _confirm_ready_in_store(store)
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    server, endpoint = start_api(service, "test-token")
    results: list[tuple[int, dict]] = []
    errors: list[BaseException] = []

    def run_confirm() -> None:
        try:
            results.append(
                _post(
                    endpoint,
                    "test-token",
                    {
                        "type": "confirm_run",
                        "research_id": "r-http",
                        "data_source_id": "yahoo_daily",
                        "unlicensed_acknowledged": True,
                    },
                )
            )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    try:
        status, body = _post(
            endpoint,
            "test-token",
            {"type": "fetch_view", "route": "#/research/r-http"},
        )
        assert status == 200
        assert body["kind"] == "confirm_run"
        assert loader.calls == 0

        first = threading.Thread(target=run_confirm, name="confirm-a")
        first.start()
        assert loader.entered.wait(timeout=2.0)
        second = threading.Thread(target=run_confirm, name="confirm-b")
        second.start()
        time.sleep(0.05)
        assert loader.calls == 1
        loader.release.set()
        first.join(timeout=5.0)
        second.join(timeout=5.0)
        assert not first.is_alive()
        assert not second.is_alive()
        assert errors == []
        assert len(results) == 2
        for code, payload in results:
            assert code == 200
            assert payload.get("code") != "internal_error"
            assert "服务器内部错误" not in json.dumps(payload, ensure_ascii=False)
            assert payload["status"] == "running"
        loaded = store.load("r-http")
        assert loaded.status is ResearchStatus.RUNNING
        assert len(loaded.versions) == 1
        assert loaded.data_window_end is not None
        assert loader.calls == 1

        status, body = _post(
            endpoint,
            "test-token",
            {"type": "fetch_view", "route": "#/research/r-http"},
        )
        assert status == 200
        assert body["kind"] == "running"
        assert loader.calls == 1
    finally:
        loader.release.set()
        server.shutdown()
        set_pool_data_loader(None)


def test_overlapping_store_writes_do_not_share_the_connection(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "shared.db")
    store.create(new_research("a", NOW))
    store.create(new_research("b", NOW))
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker(research_id: str) -> None:
        try:
            for _ in range(20):
                research = store.load(research_id)
                barrier.wait(timeout=2.0)
                updated = replace(research, updated_at=datetime.now(UTC))
                store.save(updated, research.updated_at)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=("a",)),
        threading.Thread(target=worker, args=("b",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5.0)
    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert store.load("a").research_id == "a"
    assert store.load("b").research_id == "b"
