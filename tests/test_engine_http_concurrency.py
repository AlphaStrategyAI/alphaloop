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
from engine.research.models import AssetClass, Market, Slot, Universe, new_research
from engine.research.pool_data_shrink import set_pool_data_loader
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError
from tests.test_state_machine import locked_brief

NOW = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)

pytestmark = pytest.mark.usefixtures("allow_loopback_sockets")


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
                    {"type": "confirm_run", "research_id": "r-http"},
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
    assert confirm_error["body"]["code"] == TRANSIENT_DATA_CODE


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
        service.handle({"type": "confirm_run", "research_id": "r-http"})
    elapsed = time.monotonic() - started
    set_pool_data_loader(None)

    assert exc.value.code == TRANSIENT_DATA_CODE
    assert elapsed < mdt.MARKET_DATA_LOAD_TIMEOUT_SEC + 2.0
