from alphaloop.protocol.recommend import counterpart_kind


def test_counterpart_kind_table():
    assert counterpart_kind("momentum_12_1") == "rsi"
    assert counterpart_kind("roc") == "rsi"
    assert counterpart_kind("macd") == "rsi"
    assert counterpart_kind("atr_breakout") == "rsi"
    assert counterpart_kind("rsi") == "momentum_12_1"
    assert counterpart_kind("bollinger_zscore") == "momentum_12_1"
    assert counterpart_kind("ohlr_4_pct") == "momentum_12_1"
    assert counterpart_kind("pairs_spread") == "rsi"
    assert counterpart_kind("parkinson_hist_vol") is None
    assert counterpart_kind("obv_slope") is None
    assert counterpart_kind("NotAClass") is None
