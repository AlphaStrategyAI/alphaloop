"""Target weights, the single-name cap, and cost charged when weights change.

A legacy spec has no name cap and a zero cost. That path is the historical
normalization, so a stored round replays bit for bit.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

import numpy as np
import pandas as pd

from engine.research.models import AssetClass, Market

LEGACY_COST_MODEL = "legacy_zero"
SCHEDULE_COST_MODEL = "schedule_v1"
SCHEDULE_NAME_CAP = 0.05
# Equal weight is about 5% only once at least this many names can be held.
NAME_CAP_MIN_HOLDABLE = 20


def holdable_name_cap(symbol_count: int, *, fund: bool, long_short: bool) -> float | None:
    """5% name cap, or none when the book is too small or the leg is exempt."""
    if fund or long_short or symbol_count < NAME_CAP_MIN_HOLDABLE:
        return None
    return SCHEDULE_NAME_CAP


def min_names_for_cap(cap: float) -> int:
    """Smallest equal-weight book whose weight is at most ``cap``."""
    return ceil(1.0 / cap - 1e-12)


def one_way_cost_fraction(market: Market, asset_class: AssetClass) -> float:
    """One-way cost as a fraction of traded weight. Unspecified pairs are 0.

    Charged on two-sided turnover Σ|Δw|, which already counts both the buy and
    the sell, so this rate is applied once per unit of Σ|Δw|.
    """
    if market is Market.US and asset_class is AssetClass.FUND:
        return 1.0 / 10_000
    if market is Market.US and asset_class is AssetClass.EQUITY:
        return 5.0 / 10_000
    if market is Market.CN and asset_class is AssetClass.EQUITY:
        return 20.0 / 10_000
    if market is Market.CN and asset_class is AssetClass.FUND:
        return 5.0 / 10_000
    return 0.0


def legacy_weights(signals: pd.DataFrame) -> pd.DataFrame:
    gross = signals.abs().sum(axis=1).replace(0.0, 1.0)
    return signals.div(gross, axis=0)


def _clip_redistribute(raw: np.ndarray, cap: float) -> np.ndarray:
    """Clip names above ``cap`` and give the excess to names still under it."""
    weights = np.maximum(raw.astype(float), 0.0)
    total = float(weights.sum())
    if total <= 0.0:
        return weights
    if total > 1.0:
        weights = weights / total
    for _ in range(int(weights.size) + 1):
        over = weights > cap + 1e-15
        if not bool(over.any()):
            break
        excess = float((weights[over] - cap).sum())
        weights[over] = cap
        room = np.maximum(cap - weights, 0.0)
        room[over] = 0.0
        room_sum = float(room.sum())
        if room_sum <= 1e-15:
            break
        weights = weights + room * (excess / room_sum)
    total = float(weights.sum())
    if total > 1.0 + 1e-15:
        weights = weights / total
    return weights


def _equal_weight_row(
    signal: np.ndarray,
    score: np.ndarray | None,
    cap: float,
    pool_rank: np.ndarray,
) -> np.ndarray:
    size = int(signal.size)
    active = [index for index in range(size) if float(signal[index]) > 0.0]
    out = np.zeros(size, dtype=float)
    if not active:
        return out
    magnitudes = [abs(float(signal[index])) for index in active]
    equal = max(magnitudes) - min(magnitudes) <= 1e-12
    if not equal:
        raw = np.zeros(size, dtype=float)
        for index in active:
            raw[index] = abs(float(signal[index]))
        return _clip_redistribute(raw, cap)
    chosen = list(active)
    if score is not None and (1.0 / len(chosen)) > cap:
        order = sorted(
            range(size),
            key=lambda index: (
                0 if np.isfinite(score[index]) else 1,
                -float(score[index]) if np.isfinite(score[index]) else 0.0,
                int(pool_rank[index]),
                index,
            ),
        )
        for index in order:
            if index in chosen or not np.isfinite(score[index]):
                continue
            chosen.append(index)
            if (1.0 / len(chosen)) <= cap:
                break
    weight = min(1.0 / len(chosen), cap)
    for index in chosen:
        out[index] = weight
    return out


def allocate_weights(
    signals: pd.DataFrame,
    scores: pd.DataFrame | None,
    *,
    name_cap: float | None,
    pool_symbols: tuple[str, ...] = (),
) -> pd.DataFrame:
    """Map lagged signals to weights.

    ``name_cap is None`` is the legacy book. Otherwise equal-weight books grow
    toward names already in the frame, preferring ``pool_symbols`` order on a
    tie, until each weight is at most the cap. What still does not fit is cash.
    """
    if name_cap is None:
        return legacy_weights(signals)
    columns = list(signals.columns)
    pool_pos = {symbol: index for index, symbol in enumerate(pool_symbols)}
    pool_rank = np.array([pool_pos.get(column, 10**9) for column in columns], dtype=int)
    signal_values = signals.to_numpy(dtype=float)
    score_values = None
    if scores is not None:
        score_values = scores.reindex(index=signals.index, columns=columns).to_numpy(dtype=float)
    out = np.zeros_like(signal_values, dtype=float)
    for row in range(signal_values.shape[0]):
        score_row = None if score_values is None else score_values[row]
        out[row] = _equal_weight_row(signal_values[row], score_row, float(name_cap), pool_rank)
    return pd.DataFrame(out, index=signals.index, columns=columns)


@dataclass(frozen=True, slots=True)
class DailyBook:
    gross: pd.Series
    net: pd.Series
    weights: pd.DataFrame
    cost: pd.Series


def build_book(
    weights: pd.DataFrame,
    asset_returns: pd.DataFrame,
    *,
    one_way_cost: float,
) -> DailyBook:
    gross = (weights * asset_returns).sum(axis=1).rename("strategy_return")
    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    cost = (turnover * one_way_cost).rename("cost")
    net = gross if one_way_cost == 0.0 else (gross - cost).rename("strategy_return")
    return DailyBook(gross=gross, net=net, weights=weights, cost=cost)
