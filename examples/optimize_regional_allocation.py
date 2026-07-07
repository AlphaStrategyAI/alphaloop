"""
地区分布优化 - Regional Allocation Optimization

优化全球多资产策略的地区配置权重，使用网格搜索和贝叶斯优化
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import asdict
from itertools import product

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from concurrent.futures import ProcessPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from openstrategy import BacktestEngine, BacktestConfig
from openstrategy.data.yahoo import YahooFinanceSource
from openstrategy.strategies import (
    GlobalMultiAssetStrategy,
    RebalanceTrigger,
    TacticalMethod,
)


plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")


class GridSearchOptimizer:
    """
    网格搜索优化器 - 用于地区分布参数优化
    """
    
    def __init__(
        self,
        price_data: pd.DataFrame,
        initial_capital: float = 100000.0,
        n_jobs: int = -1,
    ):
        """
        初始化网格搜索优化器
        
        Args:
            price_data: 价格数据
            initial_capital: 初始资金
            n_jobs: 并行任务数，-1表示使用所有CPU
        """
        self.price_data = price_data
        self.initial_capital = initial_capital
        self.n_jobs = os.cpu_count() if n_jobs == -1 else n_jobs
        self.results: List[Dict[str, Any]] = []
    
    def optimize_rebalance_threshold(
        self,
        thresholds: List[float] = [0.01, 0.03, 0.05, 0.07, 0.10],
        base_equity_ratio: float = 0.60,
        metric: str = "sharpe_ratio",
    ) -> Tuple[float, float, pd.DataFrame]:
        """
        优化再平衡阈值
        
        Args:
            thresholds: 待测试的阈值列表
            base_equity_ratio: 基础股债比例
            metric: 优化目标指标
            
        Returns:
            (最优阈值, 最优分数, 结果DataFrame)
        """
        logger.info(f"\n=== Optimizing Rebalance Threshold ===")
        logger.info(f"Thresholds to test: {thresholds}")
        
        results = []
        
        for threshold in thresholds:
            config = BacktestConfig(initial_cash=self.initial_capital, commission_rate=0.001)
            
            strategy = GlobalMultiAssetStrategy(
                equity_ratio=base_equity_ratio,
                bond_ratio=1.0 - base_equity_ratio,
                rebalance_trigger=RebalanceTrigger.THRESHOLD,
                rebalance_threshold=threshold,
                tactical_method=TacticalMethod.NONE,
                name=f"threshold_{threshold:.2%}",
            )
            
            engine = BacktestEngine(config)
            result = engine.run(strategy, self.price_data)
            
            score = getattr(result.metrics, metric, 0.0)
            
            results.append({
                "threshold": threshold,
                "threshold_pct": f"{threshold:.1%}",
                "score": score,
                "total_return": result.metrics.total_return,
                "cagr": result.metrics.cagr,
                "volatility": result.metrics.volatility,
                "sharpe_ratio": result.metrics.sharpe_ratio,
                "max_drawdown": result.metrics.max_drawdown,
                "calmar_ratio": result.metrics.calmar_ratio,
                "n_trades": len(result.trades),
            })
            
            logger.info(f"  Threshold {threshold:.1%}: {metric}={score:.3f}, Return={result.metrics.total_return:.2%}")
        
        df = pd.DataFrame(results)
        best_idx = df["score"].idxmax()
        best_threshold = df.loc[best_idx, "threshold"]
        best_score = df.loc[best_idx, "score"]
        
        logger.info(f"\nBest threshold: {best_threshold:.1%} with {metric}={best_score:.3f}")
        
        return best_threshold, best_score, df
    
    def optimize_stock_bond_ratio(
        self,
        ratios: List[Tuple[float, float]] = [(0.60, 0.40), (0.50, 0.50), (0.70, 0.30), (0.40, 0.60)],
        rebalance_threshold: float = 0.05,
        metric: str = "sharpe_ratio",
    ) -> Tuple[Tuple[float, float], float, pd.DataFrame]:
        """
        优化股债比例
        
        Args:
            ratios: 待测试的股债比例列表
            rebalance_threshold: 再平衡阈值
            metric: 优化目标指标
            
        Returns:
            (最优比例, 最优分数, 结果DataFrame)
        """
        logger.info(f"\n=== Optimizing Stock/Bond Ratio ===")
        logger.info(f"Ratios to test: {ratios}")
        
        results = []
        
        for equity_ratio, bond_ratio in ratios:
            config = BacktestConfig(initial_cash=self.initial_capital, commission_rate=0.001)
            
            strategy = GlobalMultiAssetStrategy(
                equity_ratio=equity_ratio,
                bond_ratio=bond_ratio,
                rebalance_trigger=RebalanceTrigger.THRESHOLD,
                rebalance_threshold=rebalance_threshold,
                tactical_method=TacticalMethod.NONE,
                name=f"equity_{equity_ratio:.0%}_bond_{bond_ratio:.0%}",
            )
            
            engine = BacktestEngine(config)
            result = engine.run(strategy, self.price_data)
            
            score = getattr(result.metrics, metric, 0.0)
            
            results.append({
                "equity_ratio": equity_ratio,
                "bond_ratio": bond_ratio,
                "ratio_label": f"{equity_ratio:.0%}/{bond_ratio:.0%}",
                "score": score,
                "total_return": result.metrics.total_return,
                "cagr": result.metrics.cagr,
                "volatility": result.metrics.volatility,
                "sharpe_ratio": result.metrics.sharpe_ratio,
                "max_drawdown": result.metrics.max_drawdown,
                "calmar_ratio": result.metrics.calmar_ratio,
                "n_trades": len(result.trades),
            })
            
            logger.info(f"  {equity_ratio:.0%}/{bond_ratio:.0%}: {metric}={score:.3f}, Return={result.metrics.total_return:.2%}")
        
        df = pd.DataFrame(results)
        best_idx = df["score"].idxmax()
        best_ratio = (df.loc[best_idx, "equity_ratio"], df.loc[best_idx, "bond_ratio"])
        best_score = df.loc[best_idx, "score"]
        
        logger.info(f"\nBest ratio: {best_ratio[0]:.0%}/{best_ratio[1]:.0%} with {metric}={best_score:.3f}")
        
        return best_ratio, best_score, df
    
    def optimize_regional_allocation(
        self,
        equity_weights_grid: List[Tuple[float, float, float, float]] = None,
        bond_weights_grid: List[Tuple[float, float, float]] = None,
        base_equity_ratio: float = 0.60,
        rebalance_threshold: float = 0.05,
        metric: str = "sharpe_ratio",
    ) -> Tuple[Dict[str, float], Dict[str, float], float, pd.DataFrame]:
        """
        优化地区分布权重
        
        Args:
            equity_weights_grid: 股票区域权重组合 [(US, Europe, Asia, EM), ...]
            bond_weights_grid: 债券类型权重组合 [(US, Intl, TIPS), ...]
            base_equity_ratio: 基础股债比例
            rebalance_threshold: 再平衡阈值
            metric: 优化目标指标
            
        Returns:
            (最优股票配置, 最优债券配置, 最优分数, 结果DataFrame)
        """
        logger.info(f"\n=== Optimizing Regional Allocation ===")
        
        # 默认股票权重网格
        if equity_weights_grid is None:
            equity_weights_grid = [
                (0.70, 0.15, 0.10, 0.05),   # US heavy
                (0.60, 0.20, 0.15, 0.05),   # Balanced (default)
                (0.50, 0.25, 0.15, 0.10),   # Diversified
                (0.40, 0.30, 0.20, 0.10),   # Global equal-ish
            ]
        
        # 默认债券权重网格
        if bond_weights_grid is None:
            bond_weights_grid = [
                (0.80, 0.10, 0.10),   # US heavy
                (0.60, 0.25, 0.15),   # Balanced
                (0.50, 0.30, 0.20),   # Diversified
            ]
        
        logger.info(f"Equity weight combinations: {len(equity_weights_grid)}")
        logger.info(f"Bond weight combinations: {len(bond_weights_grid)}")
        logger.info(f"Total combinations: {len(equity_weights_grid) * len(bond_weights_grid)}")
        
        results = []
        total = len(equity_weights_grid) * len(bond_weights_grid)
        counter = 0
        
        for eq_weights in equity_weights_grid:
            for bond_weights in bond_weights_grid:
                counter += 1
                
                us_eq, eu_eq, ap_eq, em_eq = eq_weights
                us_bd, intl_bd, tips_bd = bond_weights
                
                config = BacktestConfig(initial_cash=self.initial_capital, commission_rate=0.001)
                
                strategy = GlobalMultiAssetStrategy(
                    equity_ratio=base_equity_ratio,
                    bond_ratio=1.0 - base_equity_ratio,
                    us_weight=us_eq,
                    europe_weight=eu_eq,
                    asia_pacific_weight=ap_eq,
                    emerging_weight=em_eq,
                    us_bond_weight=us_bd,
                    international_bond_weight=intl_bd,
                    tips_weight=tips_bd,
                    rebalance_trigger=RebalanceTrigger.THRESHOLD,
                    rebalance_threshold=rebalance_threshold,
                    tactical_method=TacticalMethod.NONE,
                    name=f"regional_{counter}",
                )
                
                try:
                    engine = BacktestEngine(config)
                    result = engine.run(strategy, self.price_data)
                    
                    score = getattr(result.metrics, metric, 0.0)
                    
                    results.append({
                        "counter": counter,
                        "us_equity": us_eq,
                        "europe_equity": eu_eq,
                        "asia_pacific_equity": ap_eq,
                        "emerging_equity": em_eq,
                        "us_bond": us_bd,
                        "international_bond": intl_bd,
                        "tips": tips_bd,
                        "score": score,
                        "total_return": result.metrics.total_return,
                        "cagr": result.metrics.cagr,
                        "volatility": result.metrics.volatility,
                        "sharpe_ratio": result.metrics.sharpe_ratio,
                        "max_drawdown": result.metrics.max_drawdown,
                        "calmar_ratio": result.metrics.calmar_ratio,
                        "n_trades": len(result.trades),
                    })
                    
                    if counter % 5 == 0 or counter == total:
                        logger.info(f"  Progress: {counter}/{total} - {metric}={score:.3f}")
                        
                except Exception as e:
                    logger.warning(f"  Failed at combination {counter}: {e}")
                    continue
        
        df = pd.DataFrame(results)
        
        if df.empty:
            logger.error("No valid results from optimization!")
            return {}, {}, 0.0, df
        
        best_idx = df["score"].idxmax()
        best_equity = {
            "us": df.loc[best_idx, "us_equity"],
            "europe": df.loc[best_idx, "europe_equity"],
            "asia_pacific": df.loc[best_idx, "asia_pacific_equity"],
            "emerging": df.loc[best_idx, "emerging_equity"],
        }
        best_bond = {
            "us": df.loc[best_idx, "us_bond"],
            "international": df.loc[best_idx, "international_bond"],
            "tips": df.loc[best_idx, "tips"],
        }
        best_score = df.loc[best_idx, "score"]
        
        logger.info(f"\nBest regional allocation (score={best_score:.3f}):")
        logger.info(f"  Equity: US={best_equity['us']:.1%}, Europe={best_equity['europe']:.1%}, "
                   f"AsiaPac={best_equity['asia_pacific']:.1%}, EM={best_equity['emerging']:.1%}")
        logger.info(f"  Bond: US={best_bond['us']:.1%}, Intl={best_bond['international']:.1%}, "
                   f"TIPS={best_bond['tips']:.1%}")
        
        return best_equity, best_bond, best_score, df
    
    def optimize_tactical_method(
        self,
        methods: List[TacticalMethod] = [TacticalMethod.NONE, TacticalMethod.VOLATILITY, TacticalMethod.MOMENTUM],
        base_equity_ratio: float = 0.60,
        rebalance_threshold: float = 0.05,
        metric: str = "sharpe_ratio",
    ) -> Tuple[TacticalMethod, float, pd.DataFrame]:
        """
        优化战术资产配置方法
        
        Args:
            methods: 待测试的战术方法列表
            base_equity_ratio: 基础股债比例
            rebalance_threshold: 再平衡阈值
            metric: 优化目标指标
            
        Returns:
            (最优战术方法, 最优分数, 结果DataFrame)
        """
        logger.info(f"\n=== Optimizing Tactical Asset Allocation ===")
        logger.info(f"Methods to test: {[m.value for m in methods]}")
        
        results = []
        
        for method in methods:
            config = BacktestConfig(initial_cash=self.initial_capital, commission_rate=0.001)
            
            strategy = GlobalMultiAssetStrategy(
                equity_ratio=base_equity_ratio,
                bond_ratio=1.0 - base_equity_ratio,
                rebalance_trigger=RebalanceTrigger.THRESHOLD,
                rebalance_threshold=rebalance_threshold,
                tactical_method=method,
                name=f"tactical_{method.value}",
            )
            
            engine = BacktestEngine(config)
            result = engine.run(strategy, self.price_data)
            
            score = getattr(result.metrics, metric, 0.0)
            
            results.append({
                "method": method.value,
                "method_enum": method,
                "score": score,
                "total_return": result.metrics.total_return,
                "cagr": result.metrics.cagr,
                "volatility": result.metrics.volatility,
                "sharpe_ratio": result.metrics.sharpe_ratio,
                "max_drawdown": result.metrics.max_drawdown,
                "calmar_ratio": result.metrics.calmar_ratio,
                "n_trades": len(result.trades),
            })
            
            logger.info(f"  {method.value}: {metric}={score:.3f}, Return={result.metrics.total_return:.2%}")
        
        df = pd.DataFrame(results)
        best_idx = df["score"].idxmax()
        best_method = df.loc[best_idx, "method_enum"]
        best_score = df.loc[best_idx, "score"]
        
        logger.info(f"\nBest tactical method: {best_method.value} with {metric}={best_score:.3f}")
        
        return best_method, best_score, df
    
    def run_full_optimization(
        self,
        start_date: str = "2004-01-01",
        end_date: str = "2024-12-31",
        output_dir: str = "./results/regional_optimization",
    ) -> Dict[str, Any]:
        """
        运行完整优化流程
        
        Returns:
            优化结果字典
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info("=" * 60)
        logger.info("Regional Allocation Optimization")
        logger.info("=" * 60)
        
        # 1. 优化再平衡阈值
        best_threshold, _, threshold_df = self.optimize_rebalance_threshold(
            thresholds=[0.01, 0.03, 0.05, 0.07, 0.10],
        )
        threshold_df.to_csv(output_path / "threshold_optimization.csv", index=False)
        self._plot_threshold_results(threshold_df, output_path / "threshold_results.png")
        
        # 2. 优化股债比例
        best_ratio, _, ratio_df = self.optimize_stock_bond_ratio(
            ratios=[(0.60, 0.40), (0.50, 0.50), (0.70, 0.30), (0.40, 0.60)],
            rebalance_threshold=best_threshold,
        )
        ratio_df.to_csv(output_path / "ratio_optimization.csv", index=False)
        self._plot_ratio_results(ratio_df, output_path / "ratio_results.png")
        
        # 3. 优化地区分布
        best_equity, best_bond, _, regional_df = self.optimize_regional_allocation(
            base_equity_ratio=best_ratio[0],
            rebalance_threshold=best_threshold,
        )
        regional_df.to_csv(output_path / "regional_optimization.csv", index=False)
        self._plot_regional_results(regional_df, output_path / "regional_results.png")
        
        # 4. 优化战术方法
        best_tactical, _, tactical_df = self.optimize_tactical_method(
            base_equity_ratio=best_ratio[0],
            rebalance_threshold=best_threshold,
        )
        tactical_df.to_csv(output_path / "tactical_optimization.csv", index=False)
        self._plot_tactical_results(tactical_df, output_path / "tactical_results.png")
        
        # 汇总结果
        optimization_result = {
            "best_rebalance_threshold": best_threshold,
            "best_equity_ratio": best_ratio[0],
            "best_bond_ratio": best_ratio[1],
            "best_equity_allocation": best_equity,
            "best_bond_allocation": best_bond,
            "best_tactical_method": best_tactical.value,
            "timestamp": datetime.now().isoformat(),
        }
        
        # 保存JSON结果
        with open(output_path / "optimization_result.json", "w") as f:
            json.dump(optimization_result, f, indent=2)
        
        logger.info("\n" + "=" * 60)
        logger.info("Optimization Complete!")
        logger.info(f"Results saved to: {output_path.absolute()}")
        logger.info("=" * 60)
        
        return optimization_result
    
    def _plot_threshold_results(self, df: pd.DataFrame, save_path: str) -> None:
        """绘制阈值优化结果图"""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        axes[0, 0].bar(df["threshold"] * 100, df["sharpe_ratio"], color="steelblue")
        axes[0, 0].set_title("Sharpe Ratio by Threshold")
        axes[0, 0].set_xlabel("Threshold (%)")
        axes[0, 0].set_ylabel("Sharpe Ratio")
        axes[0, 0].grid(True, alpha=0.3)
        
        axes[0, 1].bar(df["threshold"] * 100, df["total_return"] * 100, color="green")
        axes[0, 1].set_title("Total Return by Threshold")
        axes[0, 1].set_xlabel("Threshold (%)")
        axes[0, 1].set_ylabel("Total Return (%)")
        axes[0, 1].grid(True, alpha=0.3)
        
        axes[1, 0].bar(df["threshold"] * 100, df["max_drawdown"] * 100, color="red")
        axes[1, 0].set_title("Max Drawdown by Threshold")
        axes[1, 0].set_xlabel("Threshold (%)")
        axes[1, 0].set_ylabel("Max Drawdown (%)")
        axes[1, 0].grid(True, alpha=0.3)
        
        axes[1, 1].bar(df["threshold"] * 100, df["n_trades"], color="orange")
        axes[1, 1].set_title("Number of Trades by Threshold")
        axes[1, 1].set_xlabel("Threshold (%)")
        axes[1, 1].set_ylabel("Trades")
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        plt.close()
        logger.info(f"Threshold plot saved to {save_path}")
    
    def _plot_ratio_results(self, df: pd.DataFrame, save_path: str) -> None:
        """绘制股债比例优化结果图"""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        x_labels = df["ratio_label"]
        x_pos = range(len(x_labels))
        
        axes[0, 0].bar(x_pos, df["sharpe_ratio"], color="steelblue")
        axes[0, 0].set_title("Sharpe Ratio by Stock/Bond Ratio")
        axes[0, 0].set_xticks(x_pos)
        axes[0, 0].set_xticklabels(x_labels)
        axes[0, 0].set_ylabel("Sharpe Ratio")
        axes[0, 0].grid(True, alpha=0.3)
        
        axes[0, 1].bar(x_pos, df["total_return"] * 100, color="green")
        axes[0, 1].set_title("Total Return by Stock/Bond Ratio")
        axes[0, 1].set_xticks(x_pos)
        axes[0, 1].set_xticklabels(x_labels)
        axes[0, 1].set_ylabel("Total Return (%)")
        axes[0, 1].grid(True, alpha=0.3)
        
        axes[1, 0].bar(x_pos, df["volatility"] * 100, color="purple")
        axes[1, 0].set_title("Volatility by Stock/Bond Ratio")
        axes[1, 0].set_xticks(x_pos)
        axes[1, 0].set_xticklabels(x_labels)
        axes[1, 0].set_ylabel("Volatility (%)")
        axes[1, 0].grid(True, alpha=0.3)
        
        axes[1, 1].bar(x_pos, df["calmar_ratio"], color="orange")
        axes[1, 1].set_title("Calmar Ratio by Stock/Bond Ratio")
        axes[1, 1].set_xticks(x_pos)
        axes[1, 1].set_xticklabels(x_labels)
        axes[1, 1].set_ylabel("Calmar Ratio")
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        plt.close()
        logger.info(f"Ratio plot saved to {save_path}")
    
    def _plot_regional_results(self, df: pd.DataFrame, save_path: str) -> None:
        """绘制地区分布优化结果热力图"""
        if len(df) == 0:
            return
        
        # 选择前几名显示
        top_n = min(10, len(df))
        top_df = df.nlargest(top_n, "score").reset_index(drop=True)
        
        fig, axes = plt.subplots(2, 1, figsize=(14, 12))
        
        # 股票配置热力图
        equity_cols = ["us_equity", "europe_equity", "asia_pacific_equity", "emerging_equity"]
        equity_data = top_df[equity_cols].T
        equity_data.index = ["US Equity", "Europe", "Asia Pacific", "Emerging"]
        
        sns.heatmap(equity_data, annot=True, fmt=".0%", cmap="YlOrRd", ax=axes[0],
                   cbar_kws={"label": "Weight"})
        axes[0].set_title(f"Top {top_n} Equity Allocations (by Score)")
        axes[0].set_xlabel("Configuration #")
        
        # 债券配置热力图
        bond_cols = ["us_bond", "international_bond", "tips"]
        bond_data = top_df[bond_cols].T
        bond_data.index = ["US Bonds", "Intl Bonds", "TIPS"]
        
        sns.heatmap(bond_data, annot=True, fmt=".0%", cmap="Blues", ax=axes[1],
                   cbar_kws={"label": "Weight"})
        axes[1].set_title(f"Top {top_n} Bond Allocations (by Score)")
        axes[1].set_xlabel("Configuration #")
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        plt.close()
        logger.info(f"Regional plot saved to {save_path}")
    
    def _plot_tactical_results(self, df: pd.DataFrame, save_path: str) -> None:
        """绘制战术配置优化结果图"""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        x_labels = df["method"]
        x_pos = range(len(x_labels))
        
        axes[0, 0].bar(x_pos, df["sharpe_ratio"], color="steelblue")
        axes[0, 0].set_title("Sharpe Ratio by Tactical Method")
        axes[0, 0].set_xticks(x_pos)
        axes[0, 0].set_xticklabels(x_labels, rotation=45)
        axes[0, 0].set_ylabel("Sharpe Ratio")
        axes[0, 0].grid(True, alpha=0.3)
        
        axes[0, 1].bar(x_pos, df["total_return"] * 100, color="green")
        axes[0, 1].set_title("Total Return by Tactical Method")
        axes[0, 1].set_xticks(x_pos)
        axes[0, 1].set_xticklabels(x_labels, rotation=45)
        axes[0, 1].set_ylabel("Total Return (%)")
        axes[0, 1].grid(True, alpha=0.3)
        
        axes[1, 0].bar(x_pos, df["max_drawdown"] * 100, color="red")
        axes[1, 0].set_title("Max Drawdown by Tactical Method")
        axes[1, 0].set_xticks(x_pos)
        axes[1, 0].set_xticklabels(x_labels, rotation=45)
        axes[1, 0].set_ylabel("Max Drawdown (%)")
        axes[1, 0].grid(True, alpha=0.3)
        
        axes[1, 1].bar(x_pos, df["n_trades"], color="orange")
        axes[1, 1].set_title("Number of Trades by Tactical Method")
        axes[1, 1].set_xticks(x_pos)
        axes[1, 1].set_xticklabels(x_labels, rotation=45)
        axes[1, 1].set_ylabel("Trades")
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        plt.close()
        logger.info(f"Tactical plot saved to {save_path}")


def main():
    """主函数"""
    # 加载数据
    logger.info("Loading price data...")
    data_source = YahooFinanceSource()
    
    assets = {
        "VTI": "us_equity",
        "VGK": "europe_equity",
        "VPL": "asia_pacific_equity",
        "VWO": "emerging_equity",
        "BND": "us_bond",
        "BNDX": "international_bond",
        "TIP": "tips",
    }
    
    all_data = {}
    for symbol in assets.keys():
        try:
            df = data_source.get_data(symbol, start="2004-01-01", end="2024-12-31")
            if not df.empty:
                all_data[symbol] = df['close']
                logger.info(f"  {symbol}: {len(df)} rows")
        except Exception as e:
            logger.warning(f"  {symbol}: Failed - {e}")
    
    price_data = pd.DataFrame(all_data)
    price_data = price_data.fillna(method='ffill').dropna()
    
    logger.info(f"Final dataset: {len(price_data)} days")
    
    # 运行优化
    optimizer = GridSearchOptimizer(
        price_data=price_data,
        initial_capital=100000.0,
    )
    
    result = optimizer.run_full_optimization()
    
    logger.info("\n" + "=" * 60)
    logger.info("Optimal Configuration:")
    logger.info(f"  Rebalance Threshold: {result['best_rebalance_threshold']:.1%}")
    logger.info(f"  Equity/Bond Ratio: {result['best_equity_ratio']:.0%}/{result['best_bond_ratio']:.0%}")
    logger.info(f"  Tactical Method: {result['best_tactical_method']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
