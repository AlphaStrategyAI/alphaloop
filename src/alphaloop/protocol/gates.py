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
    for name in (
        "dsr",
        "passes",
        "p_value",
        "observed_sharpe",
        "oos_sharpe_mean",
        "first_half_sharpe",
        "second_half_sharpe",
        "regime_stable",
        "oos_sharpe_median",
    ):
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


MIN_DSR_OBSERVATIONS = 30
VS_RANDOM_SIMULATIONS = 200
VS_RANDOM_BLOCK = 21


def _compute_walk_forward(
    prices: pd.Series,
    strategy_fn: Callable[[pd.Series], pd.Series],
    profile: MarketProfile,
):
    train, test, embargo = _walk_forward_windows(len(prices), profile.periods_per_year)
    return walk_forward_cv(
        prices,
        strategy_fn,
        train_size=train,
        test_size=test,
        embargo_size=embargo,
        cost_bps=profile.cost_bps,
        periods_per_year=profile.periods_per_year,
    )


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
    wf_result = None
    if HardGateName.WALK_FORWARD in required:
        try:
            wf_result = _compute_walk_forward(prices, strategy_fn, profile)
        except Exception:
            wf_result = None
    oos = wf_result.oos_returns if wf_result is not None else None
    wf_required = HardGateName.WALK_FORWARD in required
    oos_ok = isinstance(oos, pd.Series) and len(oos) > 0
    if wf_required and oos_ok:
        scored = oos
        scope = "oos_walk_forward"
    elif wf_required:
        scored = None
        scope = "oos_walk_forward"
    else:
        scored = strategy_returns
        scope = "full_sample"

    rows: list[GateResult] = []
    for name in required:
        try:
            row = _run_one(
                name,
                prices=prices,
                scored_returns=scored,
                buy_hold_prices=buy_hold_prices,
                benchmark_prices=benchmark_prices,
                secondary_frames=secondary_frames,
                n_trials=n_trials,
                profile=profile,
                seed=seed,
                wf_result=wf_result,
            )
        except Exception:
            continue
        if row is None:
            continue
        detail = dict(row.detail)
        detail["cost_bps"] = profile.cost_bps
        if name is not HardGateName.DATA_CONSISTENCY:
            detail["returns_scope"] = (
                "oos_walk_forward" if name is HardGateName.WALK_FORWARD else scope
            )
        rows.append(GateResult(name=row.name, passed=row.passed, detail=detail))
    return evaluate_hard_gates(required, rows)


def _run_one(
    name: HardGateName,
    *,
    prices: pd.Series,
    scored_returns: Optional[pd.Series],
    buy_hold_prices: pd.Series,
    benchmark_prices: pd.Series,
    secondary_frames: Optional[Mapping[str, tuple[pd.DataFrame, pd.DataFrame]]],
    n_trials: int,
    profile: MarketProfile,
    seed: int,
    wf_result,
) -> Optional[GateResult]:
    periods = profile.periods_per_year
    if name is HardGateName.DSR:
        if scored_returns is None or len(scored_returns) < MIN_DSR_OBSERVATIONS:
            return None
        observed = _annualized_sharpe(scored_returns, periods)
        result = deflated_sharpe(
            observed_sharpe=observed,
            n_trials=n_trials,
            returns=scored_returns,
        )
        return GateResult(name=name, passed=bool(result.passes), detail=_detail(result))
    if name is HardGateName.WALK_FORWARD:
        if wf_result is None:
            return None
        return GateResult(
            name=name, passed=bool(wf_result.passes), detail=_detail(wf_result)
        )
    if name is HardGateName.VS_RANDOM:
        if scored_returns is None or scored_returns.empty:
            return None
        result = vs_random(
            scored_returns,
            n_simulations=VS_RANDOM_SIMULATIONS,
            block_size=VS_RANDOM_BLOCK,
            seed=seed,
            periods_per_year=periods,
        )
        return GateResult(name=name, passed=bool(result.passes), detail=_detail(result))
    if name is HardGateName.VS_BUY_HOLD:
        if scored_returns is None or scored_returns.empty:
            return None
        result = vs_buy_hold(
            scored_returns,
            buy_hold_prices,
            periods_per_year=periods,
        )
        return GateResult(name=name, passed=bool(result.passes), detail=_detail(result))
    if name is HardGateName.VS_BENCHMARK:
        if scored_returns is None or scored_returns.empty:
            return None
        if profile.name == "us-equity-daily":
            result = vs_spy_buyhold(
                scored_returns,
                benchmark_prices,
                periods_per_year=periods,
            )
        else:
            result = vs_buy_hold(
                scored_returns,
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
