from __future__ import annotations

import math
from typing import Callable, Mapping, Optional, Sequence

import pandas as pd

from alphaloop.contracts.gates import (
    GateEvidence,
    GateResult,
    HardGateName,
    evaluate_hard_gates,
)
from alphaloop.diagnostic import (
    data_source_consistency,
    deflated_sharpe,
    vs_buy_hold,
    vs_random,
    vs_spy_buyhold,
    walk_forward_cv,
)
from alphaloop.protocol.profiles import MarketProfile


def _annualized_sharpe(returns: pd.Series, periods_per_year: int) -> float:
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1) or 0.0)
    if std <= 0.0 or not math.isfinite(std):
        return 0.0
    return float(returns.mean() / std * math.sqrt(periods_per_year))


def _detail(result: object) -> dict:
    payload: dict = {}
    for name in ("dsr", "passes", "p_value", "observed_sharpe", "oos_sharpe_mean"):
        if hasattr(result, name):
            value = getattr(result, name)
            if isinstance(value, (int, float, bool, str)):
                payload[name] = value
    return payload


def _walk_forward_windows(n: int, periods_per_year: int) -> tuple[int, int, int]:
    embargo = max(1, periods_per_year // 52)
    year = periods_per_year
    quarter = max(1, periods_per_year // 4)
    if n >= year + quarter + embargo:
        return year, quarter, embargo
    train = max(20, n // 2)
    test = max(10, n // 8)
    if n < train + embargo + test:
        raise ValueError(
            f"Need at least train+embargo+test = {train + embargo + test} bars, got {n}"
        )
    return train, test, embargo


def run_hard_gates(
    required: Sequence[HardGateName],
    *,
    prices: pd.Series,
    strategy_returns: pd.Series,
    buy_hold_prices: pd.Series,
    benchmark_prices: pd.Series,
    secondary_frames: Optional[Mapping[str, tuple[pd.DataFrame, pd.DataFrame]]],
    n_trials: int,
    profile: MarketProfile,
    seed: int,
    strategy_fn: Callable[[pd.Series], pd.Series],
) -> GateEvidence:
    rows: list[GateResult] = []
    for name in required:
        try:
            row = _run_one(
                name,
                prices=prices,
                strategy_returns=strategy_returns,
                buy_hold_prices=buy_hold_prices,
                benchmark_prices=benchmark_prices,
                secondary_frames=secondary_frames,
                n_trials=n_trials,
                profile=profile,
                seed=seed,
                strategy_fn=strategy_fn,
            )
        except Exception:
            continue
        detail = dict(row.detail)
        detail["cost_bps"] = profile.cost_bps
        rows.append(GateResult(name=row.name, passed=row.passed, detail=detail))
    return evaluate_hard_gates(required, rows)


def _run_one(
    name: HardGateName,
    *,
    prices: pd.Series,
    strategy_returns: pd.Series,
    buy_hold_prices: pd.Series,
    benchmark_prices: pd.Series,
    secondary_frames: Optional[Mapping[str, tuple[pd.DataFrame, pd.DataFrame]]],
    n_trials: int,
    profile: MarketProfile,
    seed: int,
    strategy_fn: Callable[[pd.Series], pd.Series],
) -> GateResult:
    periods = profile.periods_per_year
    if name is HardGateName.DSR:
        observed = _annualized_sharpe(strategy_returns, periods)
        result = deflated_sharpe(
            observed_sharpe=observed,
            n_trials=n_trials,
            returns=strategy_returns,
        )
        return GateResult(name=name, passed=bool(result.passes), detail=_detail(result))
    if name is HardGateName.WALK_FORWARD:
        train, test, embargo = _walk_forward_windows(len(prices), periods)
        result = walk_forward_cv(
            prices,
            strategy_fn,
            train_size=train,
            test_size=test,
            embargo_size=embargo,
            cost_bps=profile.cost_bps,
            periods_per_year=periods,
        )
        return GateResult(name=name, passed=bool(result.passes), detail=_detail(result))
    if name is HardGateName.VS_RANDOM:
        result = vs_random(
            strategy_returns,
            n_simulations=32,
            block_size=5,
            seed=seed,
            periods_per_year=periods,
        )
        return GateResult(name=name, passed=bool(result.passes), detail=_detail(result))
    if name is HardGateName.VS_BUY_HOLD:
        result = vs_buy_hold(
            strategy_returns,
            buy_hold_prices,
            periods_per_year=periods,
        )
        return GateResult(name=name, passed=bool(result.passes), detail=_detail(result))
    if name is HardGateName.VS_BENCHMARK:
        if profile.name == "us-equity-daily":
            result = vs_spy_buyhold(
                strategy_returns,
                benchmark_prices,
                periods_per_year=periods,
            )
        else:
            result = vs_buy_hold(
                strategy_returns,
                benchmark_prices,
                periods_per_year=periods,
            )
        return GateResult(name=name, passed=bool(result.passes), detail=_detail(result))
    if name is HardGateName.DATA_CONSISTENCY:
        if not secondary_frames:
            return GateResult(
                name=name,
                passed=False,
                detail={"reason": "missing_secondary_source"},
            )
        symbol, pair = next(iter(secondary_frames.items()))
        result = data_source_consistency(pair[0], pair[1], symbol=symbol)
        return GateResult(name=name, passed=bool(result.passes), detail=_detail(result))
    raise ValueError(f"unsupported hard gate: {name}")
