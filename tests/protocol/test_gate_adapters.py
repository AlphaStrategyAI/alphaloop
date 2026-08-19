from __future__ import annotations

from unittest import mock

import pandas as pd
import pytest

from alphaloop.contracts.gates import (
    HardGateName,
    evidence_from_dict,
    evidence_to_dict,
    evaluate_hard_gates,
)
from alphaloop.protocol.gates import run_hard_gates
from alphaloop.protocol.profiles import get_profile


def _prices(n: int = 80) -> pd.Series:
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.Series([100.0 + i * 0.2 for i in range(n)], index=idx, dtype=float)


def _returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change().fillna(0.0)


def _strategy_fn(series: pd.Series) -> pd.Series:
    return pd.Series(1.0, index=series.index)


def test_evidence_dict_round_trip():
    required = (HardGateName.DSR, HardGateName.VS_BUY_HOLD)
    rows = (
        {"name": "dsr", "passed": True, "detail": {"dsr": 0.9}},
        {"name": "vs_buy_hold", "passed": False, "detail": {}},
    )
    evidence = evidence_from_dict({"required": ["dsr", "vs_buy_hold"], "results": list(rows)})
    again = evidence_from_dict(evidence_to_dict(evidence))
    assert again == evidence
    assert again.required == required


def test_run_hard_gates_does_not_call_llm_judge():
    prices = _prices()
    required = (HardGateName.DSR, HardGateName.VS_BUY_HOLD)
    with mock.patch("alphaloop.diagnostic.judge.llm_judge") as judge:
        evidence = run_hard_gates(
            required,
            prices=prices,
            strategy_returns=_returns(prices),
            buy_hold_prices=prices,
            benchmark_prices=prices,
            secondary_frames={"AAPL": (pd.DataFrame({"close": prices}), pd.DataFrame({"close": prices}))},
            n_trials=1,
            profile=get_profile("us-equity-daily"),
            seed=7,
            strategy_fn=_strategy_fn,
        )
        judge.assert_not_called()
    assert {row.name for row in evidence.results} >= {HardGateName.DSR, HardGateName.VS_BUY_HOLD}


def test_us_profile_uses_spy_benchmark_adapter():
    prices = _prices()
    required = (HardGateName.VS_BENCHMARK,)
    with mock.patch("alphaloop.protocol.gates.vs_spy_buyhold") as spy, mock.patch(
        "alphaloop.protocol.gates.vs_buy_hold"
    ) as bh:
        spy.return_value = mock.Mock(passes=True)
        run_hard_gates(
            required,
            prices=prices,
            strategy_returns=_returns(prices),
            buy_hold_prices=prices,
            benchmark_prices=prices,
            secondary_frames=None,
            n_trials=1,
            profile=get_profile("us-equity-daily"),
            seed=1,
            strategy_fn=_strategy_fn,
        )
        spy.assert_called_once()
        bh.assert_not_called()


def test_crypto_profile_uses_buy_hold_against_benchmark():
    prices = _prices()
    required = (HardGateName.VS_BENCHMARK,)
    with mock.patch("alphaloop.protocol.gates.vs_spy_buyhold") as spy, mock.patch(
        "alphaloop.protocol.gates.vs_buy_hold"
    ) as bh:
        bh.return_value = mock.Mock(passes=True)
        run_hard_gates(
            required,
            prices=prices,
            strategy_returns=_returns(prices),
            buy_hold_prices=prices,
            benchmark_prices=prices,
            secondary_frames=None,
            n_trials=1,
            profile=get_profile("crypto-daily"),
            seed=1,
            strategy_fn=_strategy_fn,
        )
        bh.assert_called_once()
        spy.assert_not_called()


def test_missing_secondary_fails_data_consistency():
    prices = _prices()
    required = (HardGateName.DATA_CONSISTENCY,)
    evidence = run_hard_gates(
        required,
        prices=prices,
        strategy_returns=_returns(prices),
        buy_hold_prices=prices,
        benchmark_prices=prices,
        secondary_frames=None,
        n_trials=1,
        profile=get_profile("us-equity-daily"),
        seed=1,
        strategy_fn=_strategy_fn,
    )
    row = evidence.results[0]
    assert row.name is HardGateName.DATA_CONSISTENCY
    assert row.passed is False
    assert row.detail["reason"] == "missing_secondary_source"
    evaluate_hard_gates(required, evidence.results)
