"""
贝叶斯优化器（可选依赖）
"""

import logging
from typing import Any, Dict, List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class BayesianOptimizer:
    """
    贝叶斯优化器

    使用高斯过程进行高效的参数优化
    需要安装: pip install scikit-optimize

    Examples:
        >>> from skopt.space import Real, Integer
        >>> optimizer = BayesianOptimizer(engine)
        >>> space = {
        ...     "threshold": Real(0.01, 0.2),
        ...     "frequency_days": Integer(10, 100),
        ... }
        >>> best_params, best_score = optimizer.optimize(
        ...     strategy_class=RebalanceStrategy,
        ...     search_space=space,
        ...     data=data,
        ...     n_calls=50,
        ... )
    """

    def __init__(self, engine):
        """
        初始化贝叶斯优化器

        Args:
            engine: 回测引擎
        """
        try:
            from skopt import gp_minimize
            from skopt.space import Categorical, Integer, Real

            self._skopt_available = True
        except ImportError:
            raise ImportError(
                "scikit-optimize not installed. " "Install with: pip install scikit-optimize"
            )

        self.engine = engine
        self.results: List[Dict[str, Any]] = []

    def optimize(
        self,
        strategy_class: type,
        search_space: Dict[str, Any],
        data: pd.DataFrame,
        metric: str = "sharpe_ratio",
        maximize: bool = True,
        n_calls: int = 50,
        n_random_starts: int = 10,
    ) -> Tuple[Dict[str, Any], float]:
        """
        执行贝叶斯优化

        Args:
            strategy_class: 策略类
            search_space: 搜索空间 {param_name: skopt.space}
            data: 回测数据
            metric: 优化指标
            maximize: 是否最大化
            n_calls: 总评估次数
            n_random_starts: 随机初始化次数

        Returns:
            (最优参数, 最优分数)
        """
        from skopt import gp_minimize

        self.results = []

        param_names = list(search_space.keys())
        dimensions = list(search_space.values())

        def objective(x):
            """目标函数"""
            params = dict(zip(param_names, x))

            try:
                strategy = strategy_class(**params)
                result = self.engine.run(strategy, data)
                score = getattr(result.metrics, metric, 0.0)

                # 记录结果
                self.results.append(
                    {
                        "params": params,
                        "score": score,
                        "metrics": result.metrics,
                    }
                )

                # 如果最大化，返回负值（因为 gp_minimize 是最小化）
                return -score if maximize else score

            except Exception as e:
                logger.warning(f"Failed with params {params}: {e}")
                return 0.0 if maximize else 1e6

        logger.info(f"Bayesian optimization: {n_calls} calls")

        result = gp_minimize(
            objective,
            dimensions,
            n_calls=n_calls,
            n_random_starts=n_random_starts,
            verbose=True,
        )

        best_params = dict(zip(param_names, result.x))
        best_score = -result.fun if maximize else result.fun

        logger.info(f"Best params: {best_params}, score: {best_score:.4f}")
        return best_params, best_score

    def get_results_df(self) -> pd.DataFrame:
        """获取结果 DataFrame"""
        if not self.results:
            return pd.DataFrame()

        rows = []
        for r in self.results:
            row = {
                **{f"param_{k}": v for k, v in r["params"].items()},
                "score": r["score"],
            }
            rows.append(row)

        return pd.DataFrame(rows)
