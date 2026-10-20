import time
from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from engine.research import market_data_timeouts as mdt
from engine.research.data_availability import TRANSIENT_DATA_CODE
from engine.research.gather import (
    AkShareDataAdapter,
    RoutingDataAdapter,
    YahooDataAdapter,
    _cn_csi300_close,
    _cn_equity_close,
)
from engine.research.pool_data_shrink import set_pool_data_loader, symbols_with_daily_data

START = date(2024, 1, 1)
END = date(2024, 1, 10)


def _ohlc_frame() -> pd.DataFrame:
    index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    return pd.DataFrame({"close": [10.0, 11.0, 12.0], "date": index})


def _bond_frame() -> pd.DataFrame:
    index = pd.to_datetime(["2024-01-02", "2024-01-03"])
    return pd.DataFrame({"value": [100.0, 101.0], "date": index})


def _em_equity_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "收盘": [9.0, 9.5, 10.0],
            "日期": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
        }
    )


def test_cn_equity_prefers_sina_daily_over_eastmoney_hist() -> None:
    sina = _ohlc_frame()
    with (
        patch("engine.research.gather.ak.stock_zh_a_daily", return_value=sina) as daily,
        patch("engine.research.gather.ak.stock_zh_a_hist") as hist,
    ):
        series = _cn_equity_close("600519", "600519.SH", START, END)
        daily.assert_called_once()
        hist.assert_not_called()
    assert series.name == "600519.SH"
    assert len(series) >= 2


def test_cn_equity_falls_back_to_eastmoney_hist() -> None:
    em = _em_equity_frame()
    with (
        patch("engine.research.gather.ak.stock_zh_a_daily", side_effect=RuntimeError("sina")),
        patch("engine.research.gather.ak.stock_zh_a_hist", return_value=em) as hist,
    ):
        series = _cn_equity_close("600519", "600519.SH", START, END)
        hist.assert_called_once()
    assert len(series) >= 2


def test_csi300_prefers_sina_index_daily() -> None:
    sina = _ohlc_frame()
    with (
        patch("engine.research.gather.ak.stock_zh_index_daily", return_value=sina) as daily,
        patch("engine.research.gather.ak.stock_zh_index_daily_em") as em,
    ):
        series = _cn_csi300_close(START, END)
        daily.assert_called_once_with(symbol="sh000300")
        em.assert_not_called()
    assert series.name == "000300.SH"


def test_load_daily_cn_equity_non_empty() -> None:
    adapter = AkShareDataAdapter()
    with patch("engine.research.gather.ak.stock_zh_a_daily", return_value=_ohlc_frame()):
        frame = adapter.load_daily(("600519.SH",), START, END)
    assert not frame.empty
    assert "600519.SH" in frame.columns
    assert frame["600519.SH"].notna().any()
    assert frame.index.min() >= pd.Timestamp(START)
    assert frame.index.max() <= pd.Timestamp(END)


def test_load_daily_csi300_non_empty() -> None:
    adapter = AkShareDataAdapter()
    with patch("engine.research.gather.ak.stock_zh_index_daily", return_value=_ohlc_frame()):
        frame = adapter.load_daily(("000300.SH",), START, END)
    assert "000300.SH" in frame.columns
    assert frame["000300.SH"].notna().sum() > 0


def test_load_daily_cba_bond_fund_branches() -> None:
    adapter = AkShareDataAdapter()
    with (
        patch(
            "engine.research.gather.ak.bond_new_composite_index_cbond",
            return_value=_bond_frame(),
        ),
        patch(
            "engine.research.gather.ak.bond_zh_hs_daily",
            return_value=pd.DataFrame(
                {
                    "close": [1.0, 2.0],
                    "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
                }
            ),
        ),
        patch(
            "engine.research.gather.ak.fund_etf_hist_em",
            return_value=_em_equity_frame(),
        ),
    ):
        frame = adapter.load_daily(
            ("CBA00101.CS", "CN_BOND:123", "CN_FUND:510300"),
            START,
            END,
        )
    assert frame.shape[1] == 3
    for col in ("CBA00101.CS", "CN_BOND:123", "CN_FUND:510300"):
        assert col in frame.columns
        assert frame[col].notna().any()


def test_load_daily_forty_cn_symbols_within_default_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mdt, "MARKET_DATA_LOAD_TIMEOUT_SEC", 25.0)

    def slow_sina(*_args: object, **_kwargs: object) -> pd.DataFrame:
        time.sleep(0.35)
        return _ohlc_frame()

    symbols = tuple(f"{600000 + i:06d}.SH" for i in range(40))
    adapter = AkShareDataAdapter()
    started = time.monotonic()
    with patch("engine.research.gather.ak.stock_zh_a_daily", side_effect=slow_sina):
        frame = adapter.load_daily(symbols, START, END)
    elapsed = time.monotonic() - started
    assert frame.shape[1] == 40
    assert elapsed < mdt.MARKET_DATA_LOAD_TIMEOUT_SEC


def test_routing_timeout_still_transient_without_shrinking_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mdt, "MARKET_DATA_LOAD_TIMEOUT_SEC", 0.2)

    class _SlowAk(AkShareDataAdapter):
        def _load_daily_impl(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
            time.sleep(0.5)
            return super()._load_daily_impl(symbols, start, end)

    port = RoutingDataAdapter(YahooDataAdapter(), _SlowAk())
    with patch("engine.research.gather.ak.stock_zh_a_daily", return_value=_ohlc_frame()):
        from engine.research.user_errors import UserFacingError

        with pytest.raises(UserFacingError) as exc:
            port.load_daily(("600519.SH",), START, END)
        assert exc.value.code == "MARKET_DATA_TIMEOUT"


def test_symbols_with_daily_data_uses_non_empty_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    set_pool_data_loader(None)
    with patch("engine.research.gather.ak.stock_zh_a_daily", return_value=_ohlc_frame()):
        kept = symbols_with_daily_data(("600519.SH",), START, END)
    assert kept == ("600519.SH",)
