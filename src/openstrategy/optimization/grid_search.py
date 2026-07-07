"""
网格搜索优化器
"""

import logging
from itertools import product
from typing import Any, Dict, List, Tuple

import pandas as pd

from ..backtest.engine import BacktestEngine

logger = logging.getLogger(__name__)


class GridSearchOptimizer:
    """
    网格搜索优化器

    在参数空间上进行穷举搜索，找到最优参数组合

    Examples:
        >>> optimizer = GridSearchOptimizer(engine)
        >>> param_grid = {
        ...     "threshold": [0.03, 0.05, 0.1],
        ...     "frequency_days": [30, 60, 90],
        ... }
        >>> best_params, best_score = optimizer.optimize(
        ...     strategy_class=RebalanceStrategy,
        ...     param_grid=param_grid,
        ...     data=data,
        ...     metric="sharpe_ratio"
        ... )
    """

    def __init__(
        self,
        engine: BacktestEngine,
        n_jobs: int = 1,
    ):
        """
        初始化网格搜索优化器

        Args:
            engine: 回测引擎
            n_jobs: 并行任务数（暂未实现）
        """
        self.engine = engine
        self.n_jobs = n_jobs
        self.results: List[Dict[str, Any]] = []

    def optimize(
        self,
        strategy_class: type,
        param_grid: Dict[str, List],
        data: pd.DataFrame,
        metric: str = "sharpe_ratio",
        maximize: bool = True,
    ) -> Tuple[Dict[str, Any], float]:
        """
        执行网格搜索

        Args:
            strategy_class: 策略类
            param_grid: 参数网格 {param_name: [values]}
            data: 回测数据
            metric: 优化指标（如 "sharpe_ratio", "total_return"）
            maximize: 是否最大化指标

        Returns:
            (最优参数, 最优分数)
        """
        self.results = []

        # 生成所有参数组合
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        total_combinations = 1
        for values in param_values:
            total_combinations *= len(values)

        logger.info(f"Grid search: {total_combinations} combinations")

        best_score = float("-inf") if maximize else float("inf")
        best_params = {}

        # 遍历所有组合
        for i, values in enumerate(product(*param_values)):
            params = dict(zip(param_names, values))

            try:
                # 创建策略并回测
                strategy = strategy_class(**params)
                result = self.engine.run(strategy, data)

                # 获取指标值
                score = getattr(result.metrics, metric, 0.0)

                # 记录结果
                record = {
                    "params": params,
                    "score": score,
                    "total_return": result.metrics.total_return,
                    "sharpe_ratio": result.metrics.sharpe_ratio,
                    "max_drawdown": result.metrics.max_drawdown,
                }
                self.results.append(record)

                # 更新最优
                if maximize:
                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                else:
                    if score < best_score:
                        best_score = score
                        best_params = params.copy()

                if (i + 1) % 10 == 0:
                    logger.info(f"Progress: {i+1}/{total_combinations}")

            except Exception as e:
                logger.warning(f"Failed with params {params}: {e}")
                continue

        logger.info(f"Best params: {best_params}, score: {best_score:.4f}")
        return best_params, best_score

    def get_results_df(self) -> pd.DataFrame:
        """
        获取结果 DataFrame

        Returns:
            包含所有参数组合和结果的 DataFrame
        """
        if not self.results:
            return pd.DataFrame()

        # 展开参数字典
        rows = []
        for r in self.results:
            row = {
                **{f"param_{k}": v for k, v in r["params"].items()},
                "score": r["score"],
                "total_return": r["total_return"],
                "sharpe_ratio": r["sharpe_ratio"],
                "max_drawdown": r["max_drawdown"],
            }
            rows.append(row)

        return pd.DataFrame(rows)

    def top_n(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        获取前N个最优结果

        Args:
            n: 返回数量

        Returns:
            前N个结果
        """
        sorted_results = sorted(self.results, key=lambda x: x["score"], reverse=True)
        return sorted_results[:n]
