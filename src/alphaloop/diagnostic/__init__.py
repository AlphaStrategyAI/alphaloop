"""
alphaloop.diagnostic - Honest evaluation tools for trading strategies.

This package answers 6 questions the v1.0 goal considers mandatory
before trusting any backtest:

  1. Is the strategy overfit?    -> deflated_sharpe()
  2. Are the data sources OK?    -> data_source_consistency()
  3. Out-of-sample valid?        -> walk_forward_cv()
  4. Beats a random strategy?    -> vs_random()
  5. Beats passive holding?      -> vs_buy_hold()
  6. Beats SPY buy-and-hold?     -> vs_spy_buyhold()  (v1.0 acceptance #6)

All functions are pure (no network calls, no RNG state by default)
so they can be unit-tested offline.
"""
from .benchmarks import (
    VsBuyHoldResult,
    VsRandomResult,
    VsSpyBuyHoldResult,
    vs_buy_hold,
    vs_random,
    vs_spy_buyhold,
)
from .consistency import ConsistencyResult, data_source_consistency
from .cv import (
    CombinatorialPurgedResult,
    WalkForwardFold,
    WalkForwardResult,
    combinatorial_purged_cv,
    select_cpcv_shape,
    walk_forward_cv,
)
from .holdout import nested_holdout_bounds
from .pbo import PBOResult, probability_of_backtest_overfitting
from .dsr import DeflatedSharpeResult, deflated_sharpe, expected_max_sharpe
from .judge import DimensionScore, LLMJudgeResult, llm_judge

__all__ = [
    # DSR
    "deflated_sharpe",
    "expected_max_sharpe",
    "DeflatedSharpeResult",
    # Walk-forward CV
    "walk_forward_cv",
    "WalkForwardResult",
    "WalkForwardFold",
    "combinatorial_purged_cv",
    "select_cpcv_shape",
    "CombinatorialPurgedResult",
    "probability_of_backtest_overfitting",
    "PBOResult",
    "nested_holdout_bounds",
    # Cross-source consistency
    "data_source_consistency",
    "ConsistencyResult",
    # Benchmarks
    "vs_random",
    "vs_buy_hold",
    "vs_spy_buyhold",
    "VsRandomResult",
    "VsBuyHoldResult",
    "VsSpyBuyHoldResult",
    # Q7: LLM-as-judge (v0.6)
    "llm_judge",
    "LLMJudgeResult",
    "DimensionScore",
]
