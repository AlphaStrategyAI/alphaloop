"""zlib header failures must not stick the research on RUN_LOOP_FAILED."""

from __future__ import annotations

import pickle
import zlib
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from engine.research.clock import TimeBudget
from engine.research.data_port import BoundDataPort
from engine.research.decompress_retry import _IDENTITY, retry_on_decompress
from engine.research.frozen_input import ensure_frozen_version_input, frozen_input_path
from engine.research.loop import DefaultRoundBuilder, ResearchLoop
from engine.research.recovery_harness import PIN_END, PIN_START, seed_running
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError
from engine.review.deterministic import DeterministicReviewer
from tests.test_loop_runtime import NOW


class _Boom:
    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        return (zlib.decompress, (b"not-a-zlib-stream",))


class _Panel:
    def __init__(self) -> None:
        self.loads = 0
        self.identity = False

    def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
        del start, end
        self.loads += 1
        import requests

        self.identity = bool(getattr(requests.request, _IDENTITY, False))
        index = pd.bdate_range(PIN_START, periods=40)
        if symbols == ("SPX",):
            return pd.DataFrame({"SPX": [100.0 + i for i in range(40)]}, index=index)
        return pd.DataFrame(
            {symbol: [10.0 + i for i in range(40)] for symbol in symbols},
            index=index,
        )


class _ZlibOnce:
    def __init__(self) -> None:
        self.calls = 0

    def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
        del start, end
        self.calls += 1
        if self.calls == 1:
            raise zlib.error("Error -3 while decompressing data: incorrect header check")
        index = pd.bdate_range("2024-01-02", periods=5)
        if symbols == ("SPX",):
            return pd.DataFrame({"SPX": [1.0, 2, 3, 4, 5]}, index=index)
        return pd.DataFrame({symbol: [1.0, 2, 3, 4, 5] for symbol in symbols}, index=index)


def _research():
    from dataclasses import replace

    from engine.research.models import (
        AssetClass,
        Market,
        Slot,
        Universe,
        new_research,
    )

    research = new_research("r-zlib", NOW)
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA",))
    return replace(
        research,
        brief=replace(
            research.brief,
            thesis=Slot("mean reversion", True),
            universe=Slot(universe, True),
        ),
        data_window_start=PIN_START,
        data_window_end=PIN_END,
        data_source_id="yahoo_daily",
    )


def test_damaged_frozen_panel_is_rebuilt_from_the_same_source(tmp_path: Path) -> None:
    research = _research()
    root = tmp_path / "snapshots"
    path = frozen_input_path(root, research.research_id, 1)
    path.parent.mkdir(parents=True)
    path.write_bytes(pickle.dumps(_Boom()))
    port = _Panel()
    loaded = ensure_frozen_version_input(
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
    assert loaded.prices.shape[0] == 40
    assert port.loads == 2
    assert (path.parent / f"{path.name}.corrupt").is_file()
    again = port.loads
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
    assert port.loads == again


def test_plaintext_damage_still_does_not_silently_refetch(tmp_path: Path) -> None:
    research = _research()
    root = tmp_path / "snapshots"
    path = frozen_input_path(root, research.research_id, 1)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not a pickle")
    port = _Panel()
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
    assert port.loads == 0


def test_market_port_retries_one_zlib_header_failure() -> None:
    inner = _ZlibOnce()
    frame = BoundDataPort(inner).load_daily(("AAA",), date(2024, 1, 2), date(2024, 1, 10))
    assert inner.calls == 2
    assert frame.shape[0] == 5
    assert inner.calls == 2


def test_repeated_zlib_failure_is_a_market_data_error_not_run_loop_failed() -> None:
    class Always:
        def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
            del symbols, start, end
            raise zlib.error("Error -3 while decompressing data: incorrect header check")

    with pytest.raises(UserFacingError) as caught:
        BoundDataPort(Always()).load_daily(("AAA",), date(2024, 1, 2), date(2024, 1, 10))
    assert caught.value.code == "MARKET_DATA_FETCH_FAILED"
    assert "incorrect header check" in (caught.value.detail or "")


def test_identity_encoding_is_set_on_the_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def request(method: str, url: str, **kwargs: object) -> object:
        del method, url
        headers = kwargs.get("headers")
        assert isinstance(headers, dict)
        seen.append(str(headers.get("Accept-Encoding")))
        return object()

    import requests

    monkeypatch.setattr(requests, "request", request)
    monkeypatch.setattr(requests, "get", request)

    def once() -> str:
        import requests as requests_again

        if once.calls == 0:  # type: ignore[attr-defined]
            once.calls += 1  # type: ignore[attr-defined]
            raise zlib.error("Error -3 while decompressing data: incorrect header check")
        requests_again.request("GET", "http://example.invalid")
        return "ok"

    once.calls = 0  # type: ignore[attr-defined]
    assert retry_on_decompress(once) == "ok"
    assert seen == ["identity"]


def test_run_once_survives_a_zlib_frozen_panel(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "zlib.db")
    seed_running(store, "r-zlib", NOW)
    paths = EnginePaths.for_colocated_root(tmp_path)
    path = frozen_input_path(paths.data.snapshots_dir, "r-zlib", 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(_Boom()))
    builder = DefaultRoundBuilder(
        material_ports=(),
        data_port=_Panel(),
        start=PIN_START,
        end=PIN_END,
        snapshot_root=paths.data.snapshots_dir,
    )
    result = ResearchLoop(
        store,
        builder,
        DeterministicReviewer(),
        TimeBudget(lambda: 0.0),
        lambda: NOW,
    ).run_once("r-zlib")
    assert result.last_run_error_code != "RUN_LOOP_FAILED"
    assert any(version.rounds for version in result.versions)
