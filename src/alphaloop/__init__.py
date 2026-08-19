"""
alphaloop — local-first overnight research lab.

Honest, verifiable, agent-assisted quantitative research.
It does not promise alpha.
"""

from .__version__ import __version__

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
from .strategies import BuyHoldStrategy, RebalanceStrategy, StrategyFactory
from .engineer import (
    atr_breakout,
    bollinger_zscore,
    macd,
    momentum_12_1,
    obv_slope,
    ohlr_4_pct,
    pairs_spread,
    parkinson_hist_vol,
    roc,
    rsi,
)

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
