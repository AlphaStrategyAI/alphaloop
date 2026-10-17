from datetime import date

import pytest

from engine.research.data_errors import EmptySymbolsError
from engine.research.gather import AkShareDataAdapter, RoutingDataAdapter, YahooDataAdapter


def test_empty_symbols_raises_typed_error_instead_of_cn_routing() -> None:
    adapter = RoutingDataAdapter(YahooDataAdapter(), AkShareDataAdapter())
    with pytest.raises(EmptySymbolsError) as exc:
        adapter.load_daily((), date(2020, 1, 1), date(2021, 1, 1))
    assert exc.value.code == "DATA_SYMBOLS_EMPTY"
    assert "标的" in exc.value.message
