from __future__ import annotations

from unittest import mock

import pandas as pd
import pytest

from alphaloop.contracts.gates import (
    HardGateName,
    IncompleteEvidenceError,
    evidence_from_dict,
    evidence_to_dict,
    evaluate_hard_gates,
)
from alphaloop.protocol.gates import run_hard_gates
from alphaloop.protocol.profiles import get_profile
from alphaloop.protocol.profiles.us_equity_daily import US_EQUITY_DAILY
from alphaloop.protocol.returns import compute_strategy_returns


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


def test_walk_forward_adapter_passes_profile_cost_and_embargo():
    prices = _prices(80)
    required = (HardGateName.WALK_FORWARD,)
    with mock.patch("alphaloop.protocol.gates.walk_forward_cv") as wf:
        wf.return_value = mock.Mock(
            passes=True,
            oos_sharpe_mean=0.1,
            oos_returns=pd.Series([0.001] * 40, dtype=float),
            n_folds=1,
        )
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
        kwargs = wf.call_args.kwargs
        assert kwargs["cost_bps"] == 5.0
        assert kwargs["embargo_size"] >= 1


def test_dsr_detail_records_cost_bps():
    prices = _prices()
    evidence = run_hard_gates(
        (HardGateName.DSR,),
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
    assert evidence.results[0].detail["cost_bps"] == 5.0
    assert evidence.results[0].detail["returns_scope"] == "full_sample"


def test_high_turnover_costs_reduce_dsr_observed_sharpe():
    from dataclasses import replace

    prices = _prices(80)
    flip = pd.Series([float(i % 2) for i in range(len(prices))], index=prices.index)
    gross = compute_strategy_returns(prices, flip, cost_bps=0.0)
    net = compute_strategy_returns(prices, flip, cost_bps=1000.0)
    cheap = run_hard_gates(
        (HardGateName.DSR,),
        prices=prices,
        strategy_returns=gross,
        buy_hold_prices=prices,
        benchmark_prices=prices,
        secondary_frames=None,
        n_trials=1,
        profile=get_profile("us-equity-daily"),
        seed=1,
        strategy_fn=lambda s: flip.reindex(s.index).fillna(0.0),
    )
    expensive_profile = replace(US_EQUITY_DAILY, cost_bps=1000.0)
    expensive = run_hard_gates(
        (HardGateName.DSR,),
        prices=prices,
        strategy_returns=net,
        buy_hold_prices=prices,
        benchmark_prices=prices,
        secondary_frames=None,
        n_trials=1,
        profile=expensive_profile,
        seed=1,
        strategy_fn=lambda s: flip.reindex(s.index).fillna(0.0),
    )
    assert (
        cheap.results[0].detail["observed_sharpe"]
        > expensive.results[0].detail["observed_sharpe"]
    )
    assert expensive.results[0].detail["cost_bps"] == 1000.0


def test_dsr_uses_oos_returns_when_walk_forward_required():
    prices = _prices(80)
    oos = pd.Series(
        [0.001] * 40, index=pd.bdate_range("2020-06-01", periods=40), dtype=float
    )
    with mock.patch("alphaloop.protocol.gates.deflated_sharpe") as dsr, mock.patch(
        "alphaloop.protocol.gates.walk_forward_cv"
    ) as wf:
        wf.return_value = mock.Mock(
            passes=True, oos_sharpe_mean=0.1, oos_returns=oos, n_folds=1
        )
        dsr.return_value = mock.Mock(
            passes=True, dsr=0.99, observed_sharpe=1.0, p_value=0.01
        )
        evidence = run_hard_gates(
            (HardGateName.DSR, HardGateName.WALK_FORWARD),
            prices=prices,
            strategy_returns=_returns(prices),
            buy_hold_prices=prices,
            benchmark_prices=prices,
            secondary_frames=None,
            n_trials=2,
            profile=get_profile("us-equity-daily"),
            seed=1,
            strategy_fn=_strategy_fn,
        )
        dsr.assert_called_once()
        passed = dsr.call_args.kwargs["returns"]
        assert list(passed) == list(oos)
        by_name = {row.name: row for row in evidence.results}
        assert by_name[HardGateName.DSR].detail["returns_scope"] == "oos_walk_forward"


def test_dsr_omitted_when_oos_shorter_than_30():
    prices = _prices(80)
    oos = pd.Series(
        [0.001] * 10, index=pd.bdate_range("2020-06-01", periods=10), dtype=float
    )
    with mock.patch("alphaloop.protocol.gates.deflated_sharpe") as dsr, mock.patch(
        "alphaloop.protocol.gates.walk_forward_cv"
    ) as wf:
        wf.return_value = mock.Mock(
            passes=True, oos_sharpe_mean=0.1, oos_returns=oos, n_folds=1
        )
        with pytest.raises(IncompleteEvidenceError):
            run_hard_gates(
                (HardGateName.DSR, HardGateName.WALK_FORWARD),
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
        dsr.assert_not_called()


def test_vs_random_adapter_uses_powered_bootstrap():
    prices = _prices(80)
    with mock.patch("alphaloop.protocol.gates.vs_random") as vr:
        vr.return_value = mock.Mock(passes=True, p_value=0.1, strategy_sharpe=0.5)
        run_hard_gates(
            (HardGateName.VS_RANDOM,),
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
        assert vr.call_args.kwargs["n_simulations"] == 200
        assert vr.call_args.kwargs["block_size"] == 21
