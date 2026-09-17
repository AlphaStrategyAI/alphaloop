from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from engine.research.models import MethodRef, Universe

if TYPE_CHECKING:
    from engine.research.models import Research

Frequency = Literal["1d"]
Side = Literal["long_only", "long_short"]


@dataclass(frozen=True, slots=True)
class MarketPanel:
    prices: pd.DataFrame
    observed_at: datetime
    benchmark_prices: pd.Series | None = None

    def __post_init__(self) -> None:
        if self.prices.empty or not self.prices.index.is_monotonic_increasing:
            raise ValueError("prices must be non-empty and sorted by date")
        if self.prices.isna().all(axis=None):
            raise ValueError("prices cannot be entirely missing")


@dataclass(frozen=True, slots=True)
class StrategySpec:
    id: str
    thesis_locked: str
    universe: Universe
    frequency: Frequency
    method_set: tuple[MethodRef, ...]
    model_family: str
    lookback_days: int
    entry_z: float
    side: Side = "long_only"
    max_drawdown_floor: float = -0.25

    def __post_init__(self) -> None:
        if self.frequency != "1d":
            raise ValueError("v1 supports daily bars only")
        if not -1.0 < self.max_drawdown_floor < 0.0:
            raise ValueError("max_drawdown_floor must be between -1 and 0")


@runtime_checkable
class AlphaStrategy(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def thesis(self) -> str: ...

    @property
    def universe(self) -> Universe: ...

    @property
    def frequency(self) -> Frequency: ...

    @property
    def side(self) -> Side: ...

    def generate_signals(self, data: MarketPanel) -> pd.DataFrame:
        raise NotImplementedError

    def to_executable(self) -> Path:
        raise NotImplementedError


@dataclass(slots=True)
class MeanReversionStrategy:
    spec: StrategySpec
    data_snapshot: MarketPanel | None = None
    accepted_research: Research | None = None

    @property
    def id(self) -> str:
        return self.spec.id

    @property
    def thesis(self) -> str:
        return self.spec.thesis_locked

    @property
    def universe(self) -> Universe:
        return self.spec.universe

    @property
    def frequency(self) -> Frequency:
        return self.spec.frequency

    @property
    def side(self) -> Side:
        return self.spec.side

    def generate_signals(self, data: MarketPanel) -> pd.DataFrame:
        returns = data.prices.pct_change(fill_method=None)
        score = -returns.rolling(self.spec.lookback_days).mean()
        dispersion = score.std(axis=1).replace(0.0, np.nan)
        zscore = score.sub(score.mean(axis=1), axis=0).div(dispersion, axis=0)
        signals = pd.DataFrame(0.0, index=data.prices.index, columns=data.prices.columns)
        signals[zscore >= self.spec.entry_z] = 1.0
        if self.spec.side == "long_short":
            signals[zscore <= -self.spec.entry_z] = -1.0
        return signals

    def to_executable(self) -> Path:
        if self.data_snapshot is None or self.accepted_research is None:
            raise ValueError(
                "to_executable requires accepted Research and bundled MarketPanel snapshots"
            )
        from engine.export import build_strategy_pack

        archive = Path(tempfile.mkdtemp(prefix="alphaloop-strategy-")) / "strategy-pack.zip"
        build_strategy_pack(
            self.accepted_research,
            self,
            self.data_snapshot,
            archive,
        )
        return archive


def run_daily_backtest(strategy: AlphaStrategy, data: MarketPanel) -> pd.Series:
    signals = strategy.generate_signals(data).shift(1).fillna(0.0)
    gross = signals.abs().sum(axis=1).replace(0.0, 1.0)
    weights = signals.div(gross, axis=0)
    asset_returns = data.prices.pct_change(fill_method=None).fillna(0.0)
    return (weights * asset_returns).sum(axis=1).rename("strategy_return")
