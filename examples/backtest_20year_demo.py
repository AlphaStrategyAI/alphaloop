"""
20年回测演示 - 使用模拟数据

由于 API 限流，此版本使用高质量模拟数据进行策略演示。
数据特征基于历史统计属性。
"""

import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import numpy as np
from datetime import datetime

from alphaloop.strategies.global_multi_asset import (
    GlobalMultiAssetStrategy,
    RebalanceTrigger,
    TacticalMethod,
)
from alphaloop.strategies import BuyHoldStrategy, RebalanceStrategy
from alphaloop.core.enums import RebalanceMethod
from alphaloop.backtest import BacktestEngine, BacktestConfig
from alphaloop.backtest.report import BacktestReport

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_realistic_20year_data():
    """生成基于历史统计的20年模拟数据"""
    np.random.seed(42)
    
    # 20年交易日 (约5200天)
    dates = pd.date_range("2004-01-01", "2024-12-31", freq='B')
    n_days = len(dates)
    
    # 资产参数 (基于历史年化收益和波动率)
    assets = {
        "VTI": {"mu": 0.10, "sigma": 0.15},      # 美股
        "VGK": {"mu": 0.07, "sigma": 0.17},     # 欧股
        "VPL": {"mu": 0.06, "sigma": 0.16},     # 亚太
        "VWO": {"mu": 0.07, "sigma": 0.20},     # 新兴市场
        "BND": {"mu": 0.04, "sigma": 0.05},     # 美债
        "BNDX": {"mu": 0.03, "sigma": 0.07},    # 国际债券
        "TIP": {"mu": 0.035, "sigma": 0.06},    # 通胀保值
    }
    
    # 生成随机收益 (简化版本，不强制相关性)
    data = {}
    for symbol, params in assets.items():
        daily_mu = params["mu"] / 252
        daily_sigma = params["sigma"] / np.sqrt(252)
        
        # 生成基础收益
        returns = np.random.normal(daily_mu, daily_sigma, n_days)
        
        # 添加一些市场危机时期（2008, 2020）
        returns = add_market_stress(returns, dates, symbol)
        
        prices = 100 * np.exp(np.cumsum(returns))
        data[symbol] = prices
    
    df = pd.DataFrame(data, index=dates)
    return df


def add_market_stress(returns, dates, symbol):
    """添加市场压力时期"""
    returns = returns.copy()
    
    # 2008金融危机
    crisis_2008 = (dates >= "2008-09-01") & (dates <= "2009-03-31")
    if symbol in ["VTI", "VGK", "VPL", "VWO"]:
        returns[crisis_2008] -= 0.002  # 额外下跌
    elif symbol in ["BND", "TIP"]:
        returns[crisis_2008] += 0.0005  # 债券避险
    
    # 2020新冠
    crisis_2020 = (dates >= "2020-02-15") & (dates <= "2020-04-15")
    if symbol in ["VTI", "VGK", "VPL", "VWO"]:
        returns[crisis_2020] -= 0.003
    elif symbol in ["BND", "TIP"]:
        returns[crisis_2020] += 0.001
    
    # 2022加息周期
    rate_hike = (dates >= "2022-01-01") & (dates <= "2022-10-31")
    if symbol in ["BND", "BNDX", "TIP"]:
        returns[rate_hike] -= 0.001
    
    return returns


def main():
    print("\n" + "="*80)
    print("OpenStrategy - 20-Year Global Multi-Asset Backtest")
    print("Period: 2004-2024 (Synthetic data based on historical statistics)")
    print("="*80)
    
    # 生成数据
    logger.info("Generating 20-year synthetic market data...")
    data = generate_realistic_20year_data()
    logger.info(f"Data: {len(data)} trading days")
    logger.info(f"Period: {data.index[0].date()} to {data.index[-1].date()}")
    
    # 显示资产表现
    print("\n" + "-"*80)
    print("Asset Performance (Synthetic 2004-2024)")
    print("-"*80)
    for col in data.columns:
        total_return = (data[col].iloc[-1] / data[col].iloc[0]) - 1
        cagr = (data[col].iloc[-1] / data[col].iloc[0]) ** (1/20) - 1
        volatility = data[col].pct_change().std() * np.sqrt(252)
        print(f"{col:6s}: Return={total_return:>7.1%}  CAGR={cagr:>6.1%}  Vol={volatility:>5.1%}")
    
    # 回测配置
    config = BacktestConfig(
        initial_cash=100000.0,
        commission_rate=0.001,
        slippage=0.001,
    )
    
    # 策略
    strategies = {
        # 基准
        "Benchmark_US_60_40_BH": BuyHoldStrategy(
            symbols=["VTI", "BND"],
            weights=[0.6, 0.4],
            name="us_6040_bh",
        ),
        "Benchmark_US_60_40_Rebal": RebalanceStrategy(
            symbols=["VTI", "BND"],
            weights=[0.6, 0.4],
            method=RebalanceMethod.CALENDAR,
            frequency_days=90,
            name="us_6040_rebal",
        ),
        "Benchmark_EqualWeight": BuyHoldStrategy(
            symbols=["VTI", "VGK", "VPL", "VWO", "BND", "BNDX", "TIP"],
            weights=[1/7] * 7,
            name="equal_weight",
        ),
        
        # 全球策略
        "Global_60_40_Threshold_5pct": GlobalMultiAssetStrategy(
            equity_ratio=0.60,
            bond_ratio=0.40,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            name="global_6040_t5",
        ),
        "Global_60_40_Quarterly": GlobalMultiAssetStrategy(
            equity_ratio=0.60,
            bond_ratio=0.40,
            rebalance_trigger=RebalanceTrigger.CALENDAR,
            rebalance_frequency=90,
            name="global_6040_q",
        ),
        "Global_60_40_Monthly": GlobalMultiAssetStrategy(
            equity_ratio=0.60,
            bond_ratio=0.40,
            rebalance_trigger=RebalanceTrigger.CALENDAR,
            rebalance_frequency=30,
            name="global_6040_m",
        ),
        
        # 其他配置
        "Global_50_50_Threshold": GlobalMultiAssetStrategy(
            equity_ratio=0.50,
            bond_ratio=0.50,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            name="global_5050",
        ),
        "Global_70_30_Threshold": GlobalMultiAssetStrategy(
            equity_ratio=0.70,
            bond_ratio=0.30,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            name="global_7030",
        ),
        
        # TAA策略
        "Global_60_40_TAA_Vol": GlobalMultiAssetStrategy(
            equity_ratio=0.60,
            bond_ratio=0.40,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            tactical_method=TacticalMethod.VOLATILITY,
            lookback_days=60,
            name="global_6040_taa_vol",
        ),
        "Global_60_40_TAA_Mom": GlobalMultiAssetStrategy(
            equity_ratio=0.60,
            bond_ratio=0.40,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            tactical_method=TacticalMethod.MOMENTUM,
            lookback_days=60,
            name="global_6040_taa_mom",
        ),
    }
    
    # 运行回测
    results = {}
    engine = BacktestEngine(config)
    
    print("\n" + "="*80)
    print("Running Backtests")
    print("="*80)
    
    for name, strategy in strategies.items():
        try:
            result = engine.run(strategy, data)
            results[name] = result
            logger.info(f"{name:30s}: Return={result.metrics.total_return:>6.1%}  "
                       f"Sharpe={result.metrics.sharpe_ratio:>4.2f}  "
                       f"MaxDD={result.metrics.max_drawdown:>5.1%}")
        except Exception as e:
            logger.error(f"{name}: Failed - {e}")
    
    # 结果对比
    print("\n" + "="*80)
    print("20-Year Backtest Results Summary (2004-2024)")
    print("="*80)
    
    rows = []
    for name, result in results.items():
        m = result.metrics
        rows.append({
            "Strategy": name,
            "Return": f"{m.total_return:.1%}",
            "CAGR": f"{m.cagr:.1%}",
            "Sharpe": f"{m.sharpe_ratio:.2f}",
            "Sortino": f"{m.sortino_ratio:.2f}",
            "Max DD": f"{m.max_drawdown:.1%}",
            "Vol": f"{m.volatility:.1%}",
            "Trades": len(result.trades),
        })
    
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    
    # 找出最佳
    best_sharpe = max(results.items(), key=lambda x: x[1].metrics.sharpe_ratio)
    best_return = max(results.items(), key=lambda x: x[1].metrics.total_return)
    best_dd = min(results.items(), key=lambda x: x[1].metrics.max_drawdown)
    
    print("\n" + "-"*80)
    print("🏆 Best Performers:")
    print(f"  Best Sharpe Ratio:  {best_sharpe[0]:30s} ({best_sharpe[1].metrics.sharpe_ratio:.2f})")
    print(f"  Best Total Return:  {best_return[0]:30s} ({best_return[1].metrics.total_return:.1%})")
    print(f"  Lowest Max DD:      {best_dd[0]:30s} ({best_dd[1].metrics.max_drawdown:.1%})")
    print("-"*80)
    
    # 保存结果
    output_dir = Path(__file__).parent.parent / "results"
    output_dir.mkdir(exist_ok=True)
    
    # CSV
    df.to_csv(output_dir / "backtest_20year_synthetic.csv", index=False)
    
    # HTML报告
    for name, result in results.items():
        report = BacktestReport(result)
        safe_name = name.replace("/", "_")
        report.to_html(output_dir / f"{safe_name}_report.html")
    
    print(f"\n📁 Results saved to: {output_dir}")
    print("="*80)


if __name__ == "__main__":
    main()
