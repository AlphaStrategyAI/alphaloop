from datetime import UTC, datetime

import pandas as pd

from engine.research.models import AssetClass, Market, Universe
from engine.strategy import (
    AlphaStrategy,
    MarketPanel,
    MeanReversionStrategy,
    StrategySpec,
    run_daily_backtest,
)


def panel() -> MarketPanel:
    index = pd.date_range("2026-01-01", periods=5, tz=UTC)
    prices = pd.DataFrame(
        {"AAA": [10.0, 8.0, 9.0, 10.0, 11.0], "BBB": [10.0, 12.0, 11.0, 10.0, 9.0]},
        index=index,
    )
    return MarketPanel(prices=prices, observed_at=datetime(2026, 1, 6, tzinfo=UTC))


def strategy(side: str = "long_only") -> MeanReversionStrategy:
    universe = Universe(
        market=Market.US,
        asset_class=AssetClass.EQUITY,
        underlying_asset_class=AssetClass.EQUITY,
        symbols=("AAA", "BBB"),
    )
    spec = StrategySpec(
        id="mean-reversion-test",
        thesis_locked="one-day cross-sectional reversal",
        universe=universe,
        frequency="1d",
        side=side,
        method_set=(),
        model_family="mean_reversion",
        lookback_days=2,
        entry_z=0.5,
        max_drawdown_floor=-0.25,
    )
    return MeanReversionStrategy(spec=spec)


def test_reference_strategy_satisfies_protocol_and_signal_domain() -> None:
    instance = strategy()
    assert isinstance(instance, AlphaStrategy)

    signals = instance.generate_signals(panel())

    assert list(signals.columns) == ["AAA", "BBB"]
    assert set(signals.stack().unique()) <= {-1.0, 0.0, 1.0}
    assert (signals >= 0).all().all()


def test_long_short_reference_strategy_can_short() -> None:
    signals = strategy("long_short").generate_signals(panel())
    assert -1.0 in set(signals.stack().unique())


def test_backtest_uses_previous_day_signal_without_lookahead() -> None:
    result = run_daily_backtest(strategy(), panel())
    assert result.index.equals(panel().prices.index)
    assert result.iloc[0] == 0.0
    assert result.iloc[1] == 0.0
    assert result.notna().all()


def test_to_executable_is_part_of_the_strategy_contract() -> None:
    assert callable(strategy().to_executable)
