from datetime import date
from unittest.mock import patch

import pandas as pd

from engine.research.gather import (
    AkShareDataAdapter,
    _cn_csi300_close,
    _cn_equity_close,
)

START = date(2024, 1, 1)
END = date(2024, 1, 10)


def _frame() -> pd.DataFrame:
    index = pd.to_datetime(["2024-01-02", "2024-01-03"])
    return pd.DataFrame({"close": [10.0, 11.0], "date": index})


def test_cn_equity_prefers_sina_daily_over_eastmoney_hist() -> None:
    sina = _frame()
    em = pd.DataFrame({"收盘": [9.0, 9.5], "日期": sina["date"]})
    with (
        patch("engine.research.gather.ak.stock_zh_a_daily", return_value=sina) as daily,
        patch("engine.research.gather.ak.stock_zh_a_hist") as hist,
    ):
        series = _cn_equity_close("600519", "600519.SH", START, END)
        daily.assert_called_once()
        hist.assert_not_called()
    assert series.name == "600519.SH"
    assert len(series) == 2


def test_cn_equity_falls_back_to_eastmoney_hist() -> None:
    em = pd.DataFrame(
        {"收盘": [9.0, 9.5], "日期": pd.to_datetime(["2024-01-02", "2024-01-03"])}
    )
    with (
        patch("engine.research.gather.ak.stock_zh_a_daily", side_effect=RuntimeError("sina")),
        patch("engine.research.gather.ak.stock_zh_a_hist", return_value=em) as hist,
    ):
        series = _cn_equity_close("600519", "600519.SH", START, END)
        hist.assert_called_once()
    assert len(series) == 2


def test_csi300_prefers_sina_index_daily() -> None:
    sina = _frame()
    with (
        patch("engine.research.gather.ak.stock_zh_index_daily", return_value=sina) as daily,
        patch("engine.research.gather.ak.stock_zh_index_daily_em") as em,
    ):
        series = _cn_csi300_close(START, END)
        daily.assert_called_once_with(symbol="sh000300")
        em.assert_not_called()
    assert series.name == "000300.SH"


def test_csi300_falls_back_to_eastmoney_index() -> None:
    em = _frame()
    with (
        patch("engine.research.gather.ak.stock_zh_index_daily", side_effect=OSError("sina")),
        patch("engine.research.gather.ak.stock_zh_index_daily_em", return_value=em) as em_call,
    ):
        _cn_csi300_close(START, END)
        em_call.assert_called_once_with(symbol="sh000300")


def test_akshare_adapter_routes_600519_through_sina_helper() -> None:
    adapter = AkShareDataAdapter()
    index = pd.date_range(START, END, freq="D")
    series = pd.Series(1.0, index=index, name="600519.SH")
    with patch("engine.research.gather._cn_equity_close", return_value=series) as load:
        adapter.load_daily(("600519.SH",), START, END)
        load.assert_called_once_with("600519", "600519.SH", START, END)
