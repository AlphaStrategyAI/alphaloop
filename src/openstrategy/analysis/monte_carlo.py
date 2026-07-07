"""
蒙特卡洛模拟
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MCSimulationResult:
    """蒙特卡洛模拟结果"""

    final_values: np.ndarray
    paths: np.ndarray

    @property
    def mean_final_value(self) -> float:
        """平均最终价值"""
        return float(np.mean(self.final_values))

    @property
    def median_final_value(self) -> float:
        """中位数最终价值"""
        return float(np.median(self.final_values))

    @property
    def std_final_value(self) -> float:
        """最终价值标准差"""
        return float(np.std(self.final_values))

    @property
    def probability_of_profit(self) -> float:
        """盈利概率"""
        return float(np.mean(self.final_values > self.paths[0, 0]))

    def percentile(self, p: float) -> float:
        """
        获取分位数

        Args:
            p: 分位数 (0-100)
        """
        return float(np.percentile(self.final_values, p))

    def summary(self) -> dict:
        """结果摘要"""
        return {
            "mean": self.mean_final_value,
            "median": self.median_final_value,
            "std": self.std_final_value,
            "min": float(np.min(self.final_values)),
            "max": float(np.max(self.final_values)),
            "p5": self.percentile(5),
            "p95": self.percentile(95),
            "profit_probability": self.probability_of_profit,
        }


class MonteCarloSimulation:
    """
    蒙特卡洛模拟

    用于模拟投资组合的未来表现

    Examples:
        >>> mc = MonteCarloSimulation(returns, weights)
        >>> result = mc.simulate(n_sims=10000, years=10)
        >>> print(f"10年后中位数价值: ${result.median_final_value:,.2f}")
    """

    def __init__(
        self,
        historical_returns: pd.DataFrame,
        weights: Optional[List[float]] = None,
    ):
        """
        初始化蒙特卡洛模拟

        Args:
            historical_returns: 历史收益率 DataFrame (columns = assets)
            weights: 资产权重（默认等权）
        """
        self.returns = historical_returns
        self.assets = historical_returns.columns.tolist()

        if weights is None:
            n = len(self.assets)
            self.weights = np.array([1.0 / n] * n)
        else:
            self.weights = np.array(weights)
            # 归一化
            self.weights = self.weights / self.weights.sum()

    def simulate(
        self,
        n_sims: int = 10000,
        years: int = 10,
        initial_value: float = 100000.0,
        method: str = "bootstrap",
    ) -> MCSimulationResult:
        """
        运行蒙特卡洛模拟

        Args:
            n_sims: 模拟次数
            years: 模拟年数
            initial_value: 初始价值
            method: 模拟方法 ("bootstrap", "parametric")

        Returns:
            模拟结果
        """
        trading_days = years * 252

        if method == "bootstrap":
            paths = self._bootstrap_simulation(n_sims, trading_days, initial_value)
        elif method == "parametric":
            paths = self._parametric_simulation(n_sims, trading_days, initial_value)
        else:
            raise ValueError(f"Unknown method: {method}")

        final_values = paths[:, -1]

        return MCSimulationResult(final_values=final_values, paths=paths)

    def _bootstrap_simulation(
        self,
        n_sims: int,
        n_days: int,
        initial_value: float,
    ) -> np.ndarray:
        """
        Bootstrap 模拟（从历史数据中有放回抽样）
        """
        len(self.assets)
        n_hist = len(self.returns)

        # 生成随机索引
        random_indices = np.random.randint(0, n_hist, size=(n_sims, n_days))

        # 获取收益率
        returns_array = self.returns.values
        simulated_returns = np.zeros((n_sims, n_days))

        for i in range(n_sims):
            for t in range(n_days):
                idx = random_indices[i, t]
                daily_returns = returns_array[idx]
                # 加权组合收益
                simulated_returns[i, t] = np.dot(self.weights, daily_returns)

        # 计算累积价值
        cumulative_returns = np.cumprod(1 + simulated_returns, axis=1)
        paths = initial_value * cumulative_returns

        # 添加初始值
        initial = np.full((n_sims, 1), initial_value)
        paths = np.concatenate([initial, paths], axis=1)

        return paths

    def _parametric_simulation(
        self,
        n_sims: int,
        n_days: int,
        initial_value: float,
    ) -> np.ndarray:
        """
        参数模拟（使用均值-方差模型）
        """
        # 计算历史均值和协方差
        mean_returns = self.returns.mean().values
        cov_matrix = self.returns.cov().values

        # 组合收益均值和方差
        portfolio_mean = np.dot(self.weights, mean_returns)
        portfolio_var = np.dot(self.weights, np.dot(cov_matrix, self.weights))
        portfolio_std = np.sqrt(portfolio_var)

        # 生成随机收益率
        simulated_returns = np.random.normal(portfolio_mean, portfolio_std, size=(n_sims, n_days))

        # 计算累积价值
        cumulative_returns = np.cumprod(1 + simulated_returns, axis=1)
        paths = initial_value * cumulative_returns

        # 添加初始值
        initial = np.full((n_sims, 1), initial_value)
        paths = np.concatenate([initial, paths], axis=1)

        return paths

    def plot_distribution(self, result: MCSimulationResult, filepath: Optional[str] = None):
        """
        绘制最终价值分布图

        Args:
            result: 模拟结果
            filepath: 保存路径
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib not installed")
            return

        fig, ax = plt.subplots(figsize=(10, 6))

        ax.hist(result.final_values, bins=100, alpha=0.7, edgecolor="black")
        ax.axvline(
            result.mean_final_value,
            color="red",
            linestyle="--",
            label=f"Mean: ${result.mean_final_value:,.0f}",
        )
        ax.axvline(
            result.median_final_value,
            color="green",
            linestyle="--",
            label=f"Median: ${result.median_final_value:,.0f}",
        )

        ax.set_xlabel("Final Portfolio Value")
        ax.set_ylabel("Frequency")
        ax.set_title(f"Monte Carlo Simulation Results (n={len(result.final_values)})")
        ax.legend()
        ax.grid(True, alpha=0.3)

        if filepath:
            plt.savefig(filepath)
        else:
            plt.show()
