"""
OpenStrategy - An open-source quantitative investment research framework.

A simple, reliable framework for individual investors that prioritizes
honest evaluation over alpha promises.
"""

__version__ = "1.0.0"
__author__ = "OpenStrategy Team"

from .backtest import BacktestConfig, BacktestEngine
from .core import Asset, Portfolio, Position
from .data import AKShareSource, YahooFinanceSource
from .diagnostic import (
    DimensionScore,
    LLMJudgeResult,
    data_source_consistency,
    deflated_sharpe,
    llm_judge,
    vs_buy_hold,
    vs_random,
    vs_spy_buyhold,
    walk_forward_cv,
)
from .live import (
    AlpacaAdapter,
    Broker,
    BrokerConfig,
    CONFIRM_LIVE_FLAG,
    LiveTradingRefused,
)
from .strategies import BuyHoldStrategy, RebalanceStrategy, StrategyFactory

# v0.7 hybrid loop — imported lazily so an environment without the
# loop deps can still import the core package.
try:
    from .loop import (  # noqa: F401
        LoopRunner,
        LoopReplay,
        RunSummary,
        TaskSpec,
        BacktestResult as LoopBacktestResult,
        ScoredResult,
        RunManifest,
        TopPick,
        HybridDAG,
        Node,
        Planner,
        BacktestRunner,
        RunState,
        should_terminate,
        make_run_id,
        hash_dataframe,
    )
    _LOOP_AVAILABLE = True
except ImportError:  # pragma: no cover — defensive
    _LOOP_AVAILABLE = False

__all__ = [
    "Portfolio",
    "Asset",
    "Position",
    "BuyHoldStrategy",
    "RebalanceStrategy",
    "StrategyFactory",
    "BacktestEngine",
    "BacktestConfig",
    "YahooFinanceSource",
    "AKShareSource",
    "deflated_sharpe",
    "walk_forward_cv",
    "data_source_consistency",
    "vs_random",
    "vs_buy_hold",
    "vs_spy_buyhold",
    # v0.6: LLM-as-judge evaluator
    "llm_judge",
    "LLMJudgeResult",
    "DimensionScore",
    # engineer (alpha factors)
    "rsi",
    "macd",
    "roc",
    "momentum_12_1",
    "bollinger_zscore",
    "ohlr_4_pct",
    "pairs_spread",
    "atr_breakout",
    "parkinson_hist_vol",
    "obv_slope",
    # live (broker connectivity, hard-walled)
    "AlpacaAdapter",
    "Broker",
    "BrokerConfig",
    "CONFIRM_LIVE_FLAG",
    "LiveTradingRefused",
    # v0.7: hybrid loop
    "LoopRunner",
    "LoopReplay",
    "RunSummary",
    "TaskSpec",
    "LoopBacktestResult",
    "ScoredResult",
    "RunManifest",
    "TopPick",
    "HybridDAG",
    "Node",
    "Planner",
    "BacktestRunner",
    "RunState",
    "should_terminate",
    "make_run_id",
    "hash_dataframe",
]
