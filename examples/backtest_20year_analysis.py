"""
二十年回测分析 (2004-2024)

全球多资产策略的20年回测分析，包括:
- 多策略对比 (60/40组合, 全球等权, 买入持有)
- 完整回测报告生成
- 权益曲线、回撤图、地区配置热力图
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from openstrategy import BacktestEngine, BacktestConfig
from openstrategy.data.yahoo import YahooFinanceSource
from openstrategy.strategies import (
    BuyHoldStrategy,
    GlobalMultiAssetStrategy,
    RebalanceTrigger,
    TacticalMethod,
)


# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")


class TwentyYearBacktest:
    """
    二十年回测分析器
    
    执行2004-2024年的完整回测，生成详细报告
    """
    
    # 资产ETF映射
    ASSETS = {
        "us_equity": "VTI",           # Vanguard Total Stock Market
        "europe_equity": "VGK",       # Vanguard FTSE Europe
        "asia_pacific_equity": "VPL", # Vanguard FTSE Pacific
        "emerging_equity": "VWO",     # Vanguard FTSE Emerging Markets
        "us_bond": "BND",             # Vanguard Total Bond Market
        "international_bond": "BNDX", # Vanguard Total International Bond
        "tips": "TIP",                # iShares TIPS Bond
    }
    
    def __init__(
        self,
        start_date: str = "2004-01-01",
        end_date: str = "2024-12-31",
        initial_capital: float = 100000.0,
        output_dir: str = "./results",
    ):
        """
        初始化回测分析器
        
        Args:
            start_date: 回测开始日期
            end_date: 回测结束日期
            initial_capital: 初始资金
            output_dir: 输出目录
        """
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.data_source = YahooFinanceSource()
        self.price_data: Optional[pd.DataFrame] = None
        self.results: Dict[str, any] = {}
    
    def fetch_data(self) -> pd.DataFrame:
        """
        获取所有资产的历史数据
        
        Returns:
            价格数据DataFrame
        """
        logger.info(f"Fetching data from {self.start_date} to {self.end_date}")
        
        all_data = {}
        symbols = list(self.ASSETS.values())
        
        for symbol in symbols:
            try:
                df = self.data_source.get_data(
                    symbol=symbol,
                    start=self.start_date,
                    end=self.end_date,
                )
                
                if not df.empty:
                    # 使用调整后收盘价（包含股息再投资）
                    all_data[symbol] = df['close']
                    logger.info(f"  {symbol}: {len(df)} rows, {df['close'].iloc[0]:.2f} -> {df['close'].iloc[-1]:.2f}")
                else:
                    logger.warning(f"  {symbol}: No data available")
                    
            except Exception as e:
                logger.error(f"  {symbol}: Failed to fetch - {e}")
        
        # 合并数据
        self.price_data = pd.DataFrame(all_data)
        self.price_data.index = pd.to_datetime(self.price_data.index)
        
        # 处理缺失数据 - 前向填充
        self.price_data = self.price_data.fillna(method='ffill')
        
        # 删除全部为NaN的列
        self.price_data = self.price_data.dropna(axis=1, how='all')
        
        # 对齐起始日期 - 所有资产都有数据的第一日
        first_valid_idx = self.price_data.dropna().index[0]
        self.price_data = self.price_data.loc[first_valid_idx:]
        
        logger.info(f"Final dataset: {len(self.price_data)} days, {len(self.price_data.columns)} assets")
        logger.info(f"Date range: {self.price_data.index[0].date()} to {self.price_data.index[-1].date()}")
        
        return self.price_data
    
    def run_benchmark_6040(self) -> Dict:
        """
        运行60/40 美股/美债基准策略
        
        Returns:
            回测结果
        """
        logger.info("\n=== Running 60/40 US Benchmark ===")
        
        config = BacktestConfig(
            initial_cash=self.initial_capital,
            commission_rate=0.001,
        )
        
        strategy = GlobalMultiAssetStrategy(
            equity_ratio=0.6,
            bond_ratio=0.4,
            us_weight=1.0,       # 全部美股
            europe_weight=0.0,
            asia_pacific_weight=0.0,
            emerging_weight=0.0,
            us_bond_weight=1.0,  # 全部美债
            international_bond_weight=0.0,
            tips_weight=0.0,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            tactical_method=TacticalMethod.NONE,
            name="60_40_us_benchmark",
        )
        
        engine = BacktestEngine(config)
        result = engine.run(strategy, self.price_data)
        
        logger.info(f"Result: Return={result.metrics.total_return:.2%}, Sharpe={result.metrics.sharpe_ratio:.2f}")
        
        return {
            "name": "60/40 US Benchmark",
            "result": result,
            "strategy": strategy,
        }
    
    def run_benchmark_equal_weight(self) -> Dict:
        """
        运行全球等权基准策略
        
        Returns:
            回测结果
        """
        logger.info("\n=== Running Global Equal Weight Benchmark ===")
        
        config = BacktestConfig(
            initial_cash=self.initial_capital,
            commission_rate=0.001,
        )
        
        # 等权配置 - 股票和债券各占4/7
        strategy = GlobalMultiAssetStrategy(
            equity_ratio=4/7,
            bond_ratio=3/7,
            us_weight=0.25,
            europe_weight=0.25,
            asia_pacific_weight=0.25,
            emerging_weight=0.25,
            us_bond_weight=0.33,
            international_bond_weight=0.33,
            tips_weight=0.34,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            tactical_method=TacticalMethod.NONE,
            name="equal_weight_benchmark",
        )
        
        engine = BacktestEngine(config)
        result = engine.run(strategy, self.price_data)
        
        logger.info(f"Result: Return={result.metrics.total_return:.2%}, Sharpe={result.metrics.sharpe_ratio:.2f}")
        
        return {
            "name": "Global Equal Weight",
            "result": result,
            "strategy": strategy,
        }
    
    def run_benchmark_buy_hold(self) -> Dict:
        """
        运行买入持有基准策略
        
        Returns:
            回测结果
        """
        logger.info("\n=== Running Buy & Hold Benchmark ===")
        
        config = BacktestConfig(
            initial_cash=self.initial_capital,
            commission_rate=0.001,
        )
        
        # 使用VTI买入持有
        strategy = BuyHoldStrategy(
            symbols=["VTI"],
            weights=[1.0],
            name="buy_hold_vti",
        )
        
        engine = BacktestEngine(config)
        result = engine.run(strategy, self.price_data)
        
        logger.info(f"Result: Return={result.metrics.total_return:.2%}, Sharpe={result.metrics.sharpe_ratio:.2f}")
        
        return {
            "name": "Buy & Hold (VTI)",
            "result": result,
            "strategy": strategy,
        }
    
    def run_global_multi_asset(self) -> Dict:
        """
        运行全球多资产策略（默认配置）
        
        Returns:
            回测结果
        """
        logger.info("\n=== Running Global Multi-Asset Strategy ===")
        
        config = BacktestConfig(
            initial_cash=self.initial_capital,
            commission_rate=0.001,
        )
        
        strategy = GlobalMultiAssetStrategy(
            equity_ratio=0.60,
            bond_ratio=0.40,
            us_weight=0.60,
            europe_weight=0.20,
            asia_pacific_weight=0.15,
            emerging_weight=0.05,
            us_bond_weight=0.60,
            international_bond_weight=0.25,
            tips_weight=0.15,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            tactical_method=TacticalMethod.NONE,
            name="global_multi_asset",
        )
        
        engine = BacktestEngine(config)
        result = engine.run(strategy, self.price_data)
        
        logger.info(f"Result: Return={result.metrics.total_return:.2%}, Sharpe={result.metrics.sharpe_ratio:.2f}")
        
        return {
            "name": "Global Multi-Asset",
            "result": result,
            "strategy": strategy,
        }
    
    def run_tactical_strategy(self) -> Dict:
        """
        运行带战术资产配置的全球多资产策略
        
        Returns:
            回测结果
        """
        logger.info("\n=== Running Tactical Global Multi-Asset Strategy ===")
        
        config = BacktestConfig(
            initial_cash=self.initial_capital,
            commission_rate=0.001,
        )
        
        strategy = GlobalMultiAssetStrategy(
            equity_ratio=0.60,
            bond_ratio=0.40,
            us_weight=0.60,
            europe_weight=0.20,
            asia_pacific_weight=0.15,
            emerging_weight=0.05,
            us_bond_weight=0.60,
            international_bond_weight=0.25,
            tips_weight=0.15,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            tactical_method=TacticalMethod.MOMENTUM,
            lookback_days=60,
            name="tactical_global_multi_asset",
        )
        
        engine = BacktestEngine(config)
        result = engine.run(strategy, self.price_data)
        
        logger.info(f"Result: Return={result.metrics.total_return:.2%}, Sharpe={result.metrics.sharpe_ratio:.2f}")
        
        return {
            "name": "Tactical Global Multi-Asset",
            "result": result,
            "strategy": strategy,
        }
    
    def run_all_strategies(self) -> Dict[str, Dict]:
        """
        运行所有策略
        
        Returns:
            所有策略结果字典
        """
        if self.price_data is None:
            self.fetch_data()
        
        self.results = {
            "60_40_us": self.run_benchmark_6040(),
            "equal_weight": self.run_benchmark_equal_weight(),
            "buy_hold": self.run_benchmark_buy_hold(),
            "global_multi_asset": self.run_global_multi_asset(),
            "tactical_global": self.run_tactical_strategy(),
        }
        
        return self.results
    
    def plot_equity_curves(self, save_path: Optional[str] = None) -> None:
        """
        绘制权益曲线对比图
        
        Args:
            save_path: 保存路径
        """
        fig, ax = plt.subplots(figsize=(14, 8))
        
        colors = {
            "60_40_us": "#1f77b4",
            "equal_weight": "#ff7f0e",
            "buy_hold": "#2ca02c",
            "global_multi_asset": "#d62728",
            "tactical_global": "#9467bd",
        }
        
        for key, data in self.results.items():
            result = data["result"]
            history = result.history.set_index("date")
            
            # 归一化到初始资金
            normalized_value = history["total_value"] / self.initial_capital
            
            ax.plot(
                normalized_value.index,
                normalized_value.values,
                label=data["name"],
                color=colors.get(key, "gray"),
                linewidth=1.5,
            )
        
        ax.set_title("Portfolio Value Comparison (2004-2024)", fontsize=14, fontweight="bold")
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Portfolio Value (Normalized to $1)", fontsize=12)
        ax.legend(loc="upper left", fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # 添加 recession shading (2008, 2020)
        ax.axvspan(pd.Timestamp("2007-12-01"), pd.Timestamp("2009-06-01"), 
                   alpha=0.2, color="red", label="2008 Financial Crisis")
        ax.axvspan(pd.Timestamp("2020-02-01"), pd.Timestamp("2020-04-01"), 
                   alpha=0.2, color="red", label="COVID-19 Crash")
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            logger.info(f"Equity curve saved to {save_path}")
        else:
            plt.savefig(self.output_dir / "equity_curves.png", dpi=300, bbox_inches="tight")
        
        plt.close()
    
    def plot_drawdown(self, save_path: Optional[str] = None) -> None:
        """
        绘制回撤对比图
        
        Args:
            save_path: 保存路径
        """
        fig, ax = plt.subplots(figsize=(14, 6))
        
        colors = {
            "60_40_us": "#1f77b4",
            "equal_weight": "#ff7f0e",
            "buy_hold": "#2ca02c",
            "global_multi_asset": "#d62728",
            "tactical_global": "#9467bd",
        }
        
        for key, data in self.results.items():
            result = data["result"]
            history = result.history.set_index("date")
            
            # 计算回撤
            cummax = history["total_value"].cummax()
            drawdown = (history["total_value"] - cummax) / cummax
            
            ax.fill_between(
                drawdown.index,
                drawdown.values * 100,
                0,
                alpha=0.3,
                color=colors.get(key, "gray"),
            )
            ax.plot(
                drawdown.index,
                drawdown.values * 100,
                label=data["name"],
                color=colors.get(key, "gray"),
                linewidth=1.0,
            )
        
        ax.set_title("Drawdown Comparison (2004-2024)", fontsize=14, fontweight="bold")
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Drawdown (%)", fontsize=12)
        ax.legend(loc="lower left", fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(-60, 5)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
        else:
            plt.savefig(self.output_dir / "drawdown_comparison.png", dpi=300, bbox_inches="tight")
        
        plt.close()
    
    def plot_regional_allocation_heatmap(self, save_path: Optional[str] = None) -> None:
        """
        绘制地区配置热力图
        
        Args:
            save_path: 保存路径
        """
        # 使用全球多资产策略的历史数据
        result = self.results["global_multi_asset"]["result"]
        history = result.history.set_index("date")
        
        # 提取权重列
        weight_cols = [col for col in history.columns if col.startswith("weight_")]
        
        if not weight_cols:
            logger.warning("No weight data available for heatmap")
            return
        
        # 按年采样
        history_yearly = history.resample("Y").last()
        weights_df = history_yearly[weight_cols].T
        
        # 重命名列
        year_labels = [str(d.year) for d in weights_df.columns]
        
        # 重命名行（去除weight_前缀）
        symbol_names = {
            "weight_VTI": "US Equity",
            "weight_VGK": "Europe Equity",
            "weight_VPL": "Asia Pacific",
            "weight_VWO": "Emerging Markets",
            "weight_BND": "US Bonds",
            "weight_BNDX": "Int'l Bonds",
            "weight_TIP": "TIPS",
        }
        weights_df.index = [symbol_names.get(idx, idx) for idx in weights_df.index]
        
        fig, ax = plt.subplots(figsize=(16, 6))
        
        sns.heatmap(
            weights_df,
            annot=True,
            fmt=".1%",
            cmap="YlOrRd",
            cbar_kws={"label": "Weight"},
            ax=ax,
            linewidths=0.5,
        )
        
        ax.set_title("Regional Allocation Over Time (Yearly)", fontsize=14, fontweight="bold")
        ax.set_xlabel("Year", fontsize=12)
        ax.set_ylabel("Asset Class", fontsize=12)
        ax.set_xticklabels(year_labels, rotation=45)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
        else:
            plt.savefig(self.output_dir / "regional_allocation_heatmap.png", dpi=300, bbox_inches="tight")
        
        plt.close()
    
    def plot_rolling_metrics(self, save_path: Optional[str] = None) -> None:
        """
        绘制滚动指标图
        
        Args:
            save_path: 保存路径
        """
        fig, axes = plt.subplots(3, 1, figsize=(14, 12))
        
        window = 252  # 1年滚动窗口
        
        for key, data in self.results.items():
            result = data["result"]
            history = result.history.set_index("date")
            returns = history["total_value"].pct_change()
            
            # 滚动收益
            rolling_return = (1 + returns).rolling(window).apply(lambda x: x.prod()) - 1
            axes[0].plot(rolling_return.index, rolling_return.values * 100, 
                        label=data["name"], alpha=0.7)
            
            # 滚动波动率
            rolling_vol = returns.rolling(window).std() * np.sqrt(252) * 100
            axes[1].plot(rolling_vol.index, rolling_vol.values, 
                        label=data["name"], alpha=0.7)
            
            # 滚动夏普（简化计算，假设无风险利率为0）
            rolling_sharpe = rolling_return / (rolling_vol / 100)
            axes[2].plot(rolling_sharpe.index, rolling_sharpe.values, 
                        label=data["name"], alpha=0.7)
        
        axes[0].set_title("Rolling 1-Year Return", fontsize=12, fontweight="bold")
        axes[0].set_ylabel("Return (%)")
        axes[0].legend(loc="upper left")
        axes[0].grid(True, alpha=0.3)
        
        axes[1].set_title("Rolling 1-Year Volatility (Annualized)", fontsize=12, fontweight="bold")
        axes[1].set_ylabel("Volatility (%)")
        axes[1].legend(loc="upper left")
        axes[1].grid(True, alpha=0.3)
        
        axes[2].set_title("Rolling 1-Year Sharpe Ratio", fontsize=12, fontweight="bold")
        axes[2].set_ylabel("Sharpe Ratio")
        axes[2].set_xlabel("Date")
        axes[2].legend(loc="upper left")
        axes[2].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
        else:
            plt.savefig(self.output_dir / "rolling_metrics.png", dpi=300, bbox_inches="tight")
        
        plt.close()
    
    def generate_report(self) -> Dict:
        """
        生成回测报告
        
        Returns:
            报告数据字典
        """
        logger.info("\n=== Generating Report ===")
        
        report = {
            "backtest_period": {
                "start": self.start_date,
                "end": self.end_date,
                "initial_capital": self.initial_capital,
            },
            "strategies": {},
        }
        
        # 对比表格
        comparison_rows = []
        
        for key, data in self.results.items():
            result = data["result"]
            metrics = result.metrics
            
            strategy_report = {
                "name": data["name"],
                "total_return": metrics.total_return,
                "cagr": metrics.cagr,
                "volatility": metrics.volatility,
                "sharpe_ratio": metrics.sharpe_ratio,
                "max_drawdown": metrics.max_drawdown,
                "calmar_ratio": metrics.calmar_ratio,
                "sortino_ratio": getattr(metrics, "sortino_ratio", 0),
                "n_trades": len(result.trades),
                "final_value": result.history["total_value"].iloc[-1],
            }
            
            report["strategies"][key] = strategy_report
            
            comparison_rows.append({
                "Strategy": data["name"],
                "Total Return": f"{metrics.total_return:.2%}",
                "CAGR": f"{metrics.cagr:.2%}",
                "Volatility": f"{metrics.volatility:.2%}",
                "Sharpe": f"{metrics.sharpe_ratio:.2f}",
                "Max DD": f"{metrics.max_drawdown:.2%}",
                "Calmar": f"{metrics.calmar_ratio:.2f}",
                "Trades": len(result.trades),
            })
        
        comparison_df = pd.DataFrame(comparison_rows)
        report["comparison_table"] = comparison_df.to_dict("records")
        
        # 保存JSON报告
        json_path = self.output_dir / "backtest_report.json"
        with open(json_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"JSON report saved to {json_path}")
        
        # 保存CSV对比表
        csv_path = self.output_dir / "strategy_comparison.csv"
        comparison_df.to_csv(csv_path, index=False)
        logger.info(f"CSV comparison saved to {csv_path}")
        
        # 生成HTML报告
        self._generate_html_report(report, comparison_df)
        
        return report
    
    def _generate_html_report(self, report: Dict, comparison_df: pd.DataFrame) -> None:
        """
        生成HTML报告
        
        Args:
            report: 报告数据
            comparison_df: 对比DataFrame
        """
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>OpenStrategy - 20-Year Backtest Report (2004-2024)</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1, h2 {{
            color: #333;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            color: white;
        }}
        .info {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th {{
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
        }}
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .metric {{
            display: inline-block;
            background: white;
            padding: 15px 25px;
            margin: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-label {{
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .chart {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .chart img {{
            width: 100%;
            height: auto;
            border-radius: 5px;
        }}
        .footer {{
            text-align: center;
            color: #666;
            margin-top: 40px;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>OpenStrategy Global Multi-Asset Backtest Report</h1>
        <p>20-Year Historical Analysis (2004-2024)</p>
    </div>
    
    <div class="info">
        <h2>Backtest Configuration</h2>
        <p><strong>Period:</strong> {report["backtest_period"]["start"]} to {report["backtest_period"]["end"]}</p>
        <p><strong>Initial Capital:</strong> ${report["backtest_period"]["initial_capital"]:,.2f}</p>
        <p><strong>Commission:</strong> 0.1%</p>
    </div>
    
    <div class="info">
        <h2>Strategy Comparison</h2>
        {comparison_df.to_html(index=False, classes="comparison-table")}
    </div>
    
    <div class="chart">
        <h2>Equity Curves</h2>
        <img src="equity_curves.png" alt="Equity Curves">
    </div>
    
    <div class="chart">
        <h2>Drawdown Comparison</h2>
        <img src="drawdown_comparison.png" alt="Drawdown">
    </div>
    
    <div class="chart">
        <h2>Regional Allocation Heatmap</h2>
        <img src="regional_allocation_heatmap.png" alt="Regional Allocation">
    </div>
    
    <div class="chart">
        <h2>Rolling Metrics (1-Year Window)</h2>
        <img src="rolling_metrics.png" alt="Rolling Metrics">
    </div>
    
    <div class="footer">
        <p>Generated by OpenStrategy Framework | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
</body>
</html>
        """
        
        html_path = self.output_dir / "backtest_report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        logger.info(f"HTML report saved to {html_path}")
    
    def run_full_analysis(self) -> None:
        """运行完整分析"""
        logger.info("=" * 60)
        logger.info("OpenStrategy - 20-Year Backtest Analysis (2004-2024)")
        logger.info("=" * 60)
        
        # 1. 获取数据
        self.fetch_data()
        
        # 2. 运行所有策略
        self.run_all_strategies()
        
        # 3. 生成图表
        logger.info("\n=== Generating Charts ===")
        self.plot_equity_curves()
        self.plot_drawdown()
        self.plot_regional_allocation_heatmap()
        self.plot_rolling_metrics()
        
        # 4. 生成报告
        report = self.generate_report()
        
        logger.info("\n" + "=" * 60)
        logger.info("Analysis Complete!")
        logger.info(f"Results saved to: {self.output_dir.absolute()}")
        logger.info("=" * 60)


def main():
    """主函数"""
    backtest = TwentyYearBacktest(
        start_date="2004-01-01",
        end_date="2024-12-31",
        initial_capital=100000.0,
        output_dir="./results/twenty_year_backtest",
    )
    
    backtest.run_full_analysis()


if __name__ == "__main__":
    main()
