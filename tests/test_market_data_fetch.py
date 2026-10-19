"""v2-sized loads: scaled deadline, batches, 429 backoff, cache, structured failures."""

from __future__ import annotations

import threading
import time
from datetime import date

import pandas as pd
import pytest

from engine.research import market_data_timeouts as mdt
from engine.research.data_availability import market_data_timeout
from engine.research.gather import (
    AkShareDataAdapter,
    YahooDataAdapter,
    _note_retry_after,
    _yahoo_history,
)
from engine.research.market_data_progress import (
    market_data_progress,
    market_data_progress_payload,
    set_market_data_progress,
)
from engine.research.market_data_retry import (
    call_with_rate_limit_retry,
    retry_after_seconds,
)
from engine.research.price_cache import get_cached_close, put_cached_close
from engine.research.user_errors import UserFacingError

START = date(2024, 1, 2)
END = date(2024, 1, 4)


def _bars(symbols: list[str]) -> pd.DataFrame:
    index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    return pd.DataFrame({symbol: pd.Series([1.0, 2.0, 3.0], index=index) for symbol in symbols})


def test_builtin_deadline_scales_with_v2_pool_sizes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mdt, "MARKET_DATA_LOAD_TIMEOUT_SEC", mdt._BUILTIN_MARKET_DATA_TIMEOUT_SEC)
    monkeypatch.setattr(mdt, "_SEC_PER_BATCH", mdt.DEFAULT_SEC_PER_BATCH)
    monkeypatch.delenv("ALPHALOOP_CN_MARKET_MAX_WORKERS", raising=False)
    assert mdt.DEFAULT_SEC_PER_BATCH == 60
    assert mdt.YAHOO_BATCH_SIZE == 40
    assert mdt.YAHOO_FETCH_CONCURRENCY == 2
    assert mdt.cn_market_data_max_workers() == 8
    # 503 / 40 batches, 300 / 8 waves. The old 25s cap cannot finish either pool.
    assert mdt.load_deadline_seconds(503, batch_size=40) == 13 * 60
    assert mdt.load_deadline_seconds(300, batch_size=8) == 38 * 60


def test_explicit_timeout_override_stays_a_hard_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mdt, "MARKET_DATA_LOAD_TIMEOUT_SEC", 0.5)
    assert mdt.load_deadline_seconds(503, batch_size=40) == 0.5


def test_retry_after_header_beats_exponential_backoff() -> None:
    error = type("Rate", (Exception,), {})("429")
    error.response = type("Resp", (), {"status_code": 429, "headers": {"Retry-After": "7"}})()
    assert retry_after_seconds(error, 0) == 7.0
    plain = type("Rate", (Exception,), {})("HTTP 429")
    assert retry_after_seconds(plain, 2) == 4.0


def test_rate_limit_retries_then_raises_structured_code() -> None:
    sleeps: list[float] = []
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        error = type("Rate", (Exception,), {})("Too Many Requests")
        error.response = type("Resp", (), {"status_code": 429, "headers": {"Retry-After": "0"}})()
        raise error

    with pytest.raises(UserFacingError) as exc:
        call_with_rate_limit_retry(flaky, attempts=3, sleep=sleeps.append)
    assert exc.value.code == "MARKET_DATA_RATE_LIMITED"
    assert calls["n"] == 3
    assert sleeps == [0.0, 0.0]


def test_yahoo_downloads_in_batches_and_skips_cached_symbols(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    inflight = {"n": 0, "max": 0}
    finished: set[str] = set()
    lock = threading.Lock()

    def fake_history(symbol: str, _start: date, _end: date) -> pd.Series:
        with lock:
            if symbol == "S4":
                assert finished >= {"S0", "S1", "S2", "S3"}
            inflight["n"] += 1
            inflight["max"] = max(inflight["max"], inflight["n"])
            calls.append(symbol)
        try:
            time.sleep(0.02)
            return _bars([symbol])[symbol]
        finally:
            with lock:
                inflight["n"] -= 1
                finished.add(symbol)

    monkeypatch.setattr("engine.research.gather._yahoo_history", fake_history)
    monkeypatch.setattr("engine.research.gather.YAHOO_BATCH_SIZE", 4)
    monkeypatch.setattr("engine.research.gather.YAHOO_FETCH_CONCURRENCY", 2)
    symbols = tuple(f"S{i}" for i in range(6))
    adapter = YahooDataAdapter()
    frame = adapter.load_daily(symbols, START, END)
    assert list(frame.columns) == list(symbols)
    assert calls.count("S0") == 1
    assert set(calls) == set(symbols)
    assert inflight["max"] <= 2
    assert market_data_progress() is None
    calls.clear()
    again = adapter.load_daily(symbols, START, END)
    assert calls == []
    assert list(again.columns) == list(symbols)


def test_akshare_does_not_refetch_cached_names(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_daily(*_args: object, **kwargs: object) -> pd.DataFrame:
        symbol = str(kwargs["symbol"])
        calls.append(symbol)
        index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
        return pd.DataFrame({"close": [1.0, 2.0, 3.0], "date": index})

    monkeypatch.setattr("engine.research.gather.ak.stock_zh_a_daily", fake_daily)
    adapter = AkShareDataAdapter()
    symbols = ("600519.SH", "000001.SZ")
    adapter.load_daily(symbols, START, END)
    assert len(calls) == 2
    calls.clear()
    adapter.load_daily(symbols, START, END)
    assert calls == []


def test_akshare_symbol_failure_is_a_structured_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_daily(*_args: object, **kwargs: object) -> pd.DataFrame:
        if str(kwargs["symbol"]).endswith("000001"):
            raise RuntimeError("upstream down")
        index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
        return pd.DataFrame({"close": [1.0, 2.0, 3.0], "date": index})

    monkeypatch.setattr("engine.research.gather.ak.stock_zh_a_daily", fake_daily)
    with pytest.raises(UserFacingError) as exc:
        AkShareDataAdapter().load_daily(("600519.SH", "000001.SZ"), START, END)
    assert exc.value.code == "MARKET_DATA_FETCH_FAILED"
    assert "000001.SZ" in exc.value.message


def _rate_limit(retry_after: str) -> Exception:
    error = type("Rate", (Exception,), {})("Too Many Requests")
    error.response = type("Resp", (), {"status_code": 429, "headers": {"Retry-After": retry_after}})()
    return error


def test_yahoo_rate_limit_is_structured_and_does_not_return_a_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_history(symbol: str, _start: date, _end: date) -> pd.Series:
        raise _rate_limit("0")

    monkeypatch.setattr("engine.research.gather._yahoo_history", fake_history)
    with pytest.raises(UserFacingError) as exc:
        YahooDataAdapter().load_daily(("AAPL", "MSFT"), START, END)
    assert exc.value.code == "MARKET_DATA_RATE_LIMITED"
    assert "MARKET_DATA_RATE_LIMITED" in exc.value.message
    assert get_cached_close("yahoo", "AAPL", START, END) is None


def test_yahoo_other_failure_names_the_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_history(symbol: str, _start: date, _end: date) -> pd.Series:
        if symbol == "MSFT":
            raise RuntimeError("connection reset")
        return _bars([symbol])[symbol]

    monkeypatch.setattr("engine.research.gather._yahoo_history", fake_history)
    with pytest.raises(UserFacingError) as exc:
        YahooDataAdapter().load_daily(("AAPL", "MSFT"), START, END)
    assert exc.value.code == "MARKET_DATA_FETCH_FAILED"
    assert "MSFT" in exc.value.message
    assert "MARKET_DATA_FETCH_FAILED" in exc.value.message


def test_yahoo_history_keeps_retry_after_and_treats_missing_prices_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    from yfinance.exceptions import YFPricesMissingError, YFRateLimitError

    class FakeTicker:
        def __init__(self, symbol: str, session: object = None) -> None:
            self.symbol = symbol

        def history(self, **_kwargs: object) -> pd.DataFrame:
            if self.symbol == "GONE":
                raise YFPricesMissingError("GONE", "no rows")
            response = type("Resp", (), {"status_code": 429, "headers": {"Retry-After": "9"}})()
            _note_retry_after(response)
            raise YFRateLimitError()

    monkeypatch.setattr("engine.research.gather.yf.Ticker", FakeTicker)
    monkeypatch.setattr("engine.research.gather._install_yahoo_retry_after_capture", lambda: None)
    assert _yahoo_history("GONE", START, END).empty
    with pytest.raises(Exception) as exc:
        _yahoo_history("AAPL", START, END)
    assert retry_after_seconds(exc.value, 0) == 9.0


def test_akshare_rate_limit_does_not_fall_through_to_the_other_source(monkeypatch: pytest.MonkeyPatch) -> None:
    hist_calls: list[str] = []

    def fake_daily(*_args: object, **_kwargs: object) -> pd.DataFrame:
        raise _rate_limit("0")

    def fake_hist(*_args: object, **kwargs: object) -> pd.DataFrame:
        hist_calls.append(str(kwargs.get("symbol")))
        index = pd.to_datetime(["2024-01-02"])
        return pd.DataFrame({"收盘": [1.0], "日期": index})

    monkeypatch.setattr("engine.research.gather.ak.stock_zh_a_daily", fake_daily)
    monkeypatch.setattr("engine.research.gather.ak.stock_zh_a_hist", fake_hist)
    with pytest.raises(UserFacingError) as exc:
        AkShareDataAdapter().load_daily(("600519.SH",), START, END)
    assert exc.value.code == "MARKET_DATA_RATE_LIMITED"
    assert hist_calls == []


def test_timeout_message_carries_the_code() -> None:
    error = market_data_timeout(503)
    assert error.code == "MARKET_DATA_TIMEOUT"
    assert "503" in error.message
    assert "MARKET_DATA_TIMEOUT" in error.message


def test_progress_payload_is_readable_while_a_load_is_in_flight() -> None:
    set_market_data_progress(12, 503, "yahoo")
    assert market_data_progress_payload() == {"done": 12, "total": 503, "source": "yahoo"}


def test_cache_roundtrip_does_not_store_weights(tmp_path) -> None:
    from engine.research.price_cache import set_price_cache_dir

    set_price_cache_dir(tmp_path)
    series = _bars(["AAPL"])["AAPL"]
    put_cached_close("yahoo", "AAPL", START, END, series)
    loaded = get_cached_close("yahoo", "AAPL", START, END)
    assert loaded is not None
    text = (tmp_path / "yahoo" / "AAPL.csv").read_text(encoding="utf-8")
    assert "weight" not in text
    narrower = get_cached_close("yahoo", "AAPL", date(2024, 1, 3), date(2024, 1, 3))
    assert narrower is not None
    assert len(narrower) == 1
    assert get_cached_close("yahoo", "AAPL", START, date(2024, 1, 5)) is None
