"""
全球多资产策略演示 - Global Multi-Asset Strategy Demo

展示 GlobalMultiAssetStrategy 的使用方法和功能特性
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

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
    RegionalAllocation,
    AssetMapping,
)


def demo_basic_strategy():
    """
    演示1: 基础全球多资产策略
    
    创建一个标准的60/40全球分散投资组合
    """
    logger.info("\n" + "=" * 60)
    logger.info("Demo 1: Basic Global Multi-Asset Strategy (60/40)")
    logger.info("=" * 60)
    
    # 获取数据
    data_source = YahooFinanceSource()
    symbols = ["VTI", "VGK", "VPL", "VWO", "BND", "BNDX", "TIP"]
    
    all_data = {}
    for symbol in symbols:
        try:
            df = data_source.get_data(symbol, period="5y")
            all_data[symbol] = df['close']
            logger.info(f"  Loaded {symbol}: {len(df)} rows")
        except Exception as e:
            logger.warning(f"  Failed to load {symbol}: {e}")
    
    price_data = pd.DataFrame(all_data).fillna(method='ffill').dropna()
    
    # 创建策略
    strategy = GlobalMultiAssetStrategy(
        name="demo_basic_6040",
        equity_ratio=0.60,    # 60% 股票
        bond_ratio=0.40,      # 40% 债券
        # 股票区域分布（在股票部分的权重）
        us_weight=0.60,       # 美股 60% of equity
        europe_weight=0.20,   # 欧股 20% of equity
        asia_pacific_weight=0.15,  # 亚太 15% of equity
        emerging_weight=0.05, # 新兴市场 5% of equity
        # 债券类型分布（在债券部分的权重）
        us_bond_weight=0.60,  # 美债 60% of bonds
        international_bond_weight=0.25,  # 国际债券 25% of bonds
        tips_weight=0.15,     # TIPS 15% of bonds
        # 再平衡设置
        rebalance_trigger=RebalanceTrigger.THRESHOLD,
        rebalance_threshold=0.05,  # 5%偏离阈值
    )
    
    # 显示策略摘要
    logger.info(f"\nStrategy Summary:")
    summary = strategy.get_summary()
    for key, value in summary.items():
        logger.info(f"  {key}: {value}")
    
    # 运行回测
    config = BacktestConfig(
        initial_cash=100000.0,
        commission_rate=0.001,
    )
    
    engine = BacktestEngine(config)
    result = engine.run(strategy, price_data)
    
    # 显示结果
    logger.info(f"\nBacktest Results:")
    logger.info(f"  Total Return: {result.metrics.total_return:.2%}")
    logger.info(f"  CAGR: {result.metrics.cagr:.2%}")
    logger.info(f"  Sharpe Ratio: {result.metrics.sharpe_ratio:.2f}")
    logger.info(f"  Max Drawdown: {result.metrics.max_drawdown:.2%}")
    logger.info(f"  Volatility: {result.metrics.volatility:.2%}")
    logger.info(f"  Number of Trades: {len(result.trades)}")
    
    return result


def demo_rebalance_triggers():
    """
    演示2: 不同再平衡触发方式的对比
    
    比较阈值触发、日历触发和两者结合的效果
    """
    logger.info("\n" + "=" * 60)
    logger.info("Demo 2: Rebalance Trigger Comparison")
    logger.info("=" * 60)
    
    # 获取数据
    data_source = YahooFinanceSource()
    symbols = ["VTI", "VGK", "VPL", "VWO", "BND", "BNDX", "TIP"]
    
    all_data = {}
    for symbol in symbols:
        try:
            df = data_source.get_data(symbol, period="5y")
            all_data[symbol] = df['close']
        except Exception as e:
            logger.warning(f"  Failed to load {symbol}: {e}")
    
    price_data = pd.DataFrame(all_data).fillna(method='ffill').dropna()
    
    triggers = [
        (RebalanceTrigger.THRESHOLD, "Threshold (5%)"),
        (RebalanceTrigger.CALENDAR, "Calendar (Monthly)"),
        (RebalanceTrigger.BOTH, "Both Combined"),
    ]
    
    results = []
    
    for trigger, name in triggers:
        strategy = GlobalMultiAssetStrategy(
            name=f"demo_{trigger.value}",
            equity_ratio=0.60,
            bond_ratio=0.40,
            rebalance_trigger=trigger,
            rebalance_threshold=0.05,
            rebalance_frequency=30,
        )
        
        config = BacktestConfig(initial_cash=100000.0, commission_rate=0.001)
        engine = BacktestEngine(config)
        result = engine.run(strategy, price_data)
        
        results.append({
            "Trigger": name,
            "Return": result.metrics.total_return,
            "Sharpe": result.metrics.sharpe_ratio,
            "Max DD": result.metrics.max_drawdown,
            "Trades": len(result.trades),
        })
        
        logger.info(f"  {name}: Return={result.metrics.total_return:.2%}, "
                   f"Sharpe={result.metrics.sharpe_ratio:.2f}, "
                   f"Trades={len(result.trades)}")
    
    # 创建对比表
    df = pd.DataFrame(results)
    logger.info(f"\nComparison Table:")
    logger.info("\n" + df.to_string(index=False))
    
    return results


def demo_tactical_allocation():
    """
    演示3: 战术资产配置效果
    
    展示基于动量和波动率的战术调整效果
    """
    logger.info("\n" + "=" * 60)
    logger.info("Demo 3: Tactical Asset Allocation")
    logger.info("=" * 60)
    
    # 获取数据
    data_source = YahooFinanceSource()
    symbols = ["VTI", "VGK", "VPL", "VWO", "BND", "BNDX", "TIP"]
    
    all_data = {}
    for symbol in symbols:
        try:
            df = data_source.get_data(symbol, period="5y")
            all_data[symbol] = df['close']
        except Exception as e:
            logger.warning(f"  Failed to load {symbol}: {e}")
    
    price_data = pd.DataFrame(all_data).fillna(method='ffill').dropna()
    
    methods = [
        (TacticalMethod.NONE, "No Tactical Adjustment"),
        (TacticalMethod.VOLATILITY, "Volatility-Based"),
        (TacticalMethod.MOMENTUM, "Momentum-Based"),
        (TacticalMethod.RISK_PARITY, "Risk Parity"),
    ]
    
    results = []
    
    for method, name in methods:
        strategy = GlobalMultiAssetStrategy(
            name=f"demo_tactical_{method.value}",
            equity_ratio=0.60,
            bond_ratio=0.40,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            tactical_method=method,
            lookback_days=60,
            volatility_target=0.10,
        )
        
        config = BacktestConfig(initial_cash=100000.0, commission_rate=0.001)
        engine = BacktestEngine(config)
        result = engine.run(strategy, price_data)
        
        results.append({
            "Method": name,
            "Return": result.metrics.total_return,
            "Sharpe": result.metrics.sharpe_ratio,
            "Max DD": result.metrics.max_drawdown,
            "Volatility": result.metrics.volatility,
        })
        
        logger.info(f"  {name}: Return={result.metrics.total_return:.2%}, "
                   f"Sharpe={result.metrics.sharpe_ratio:.2f}, "
                   f"Vol={result.metrics.volatility:.2%}")
    
    # 创建对比表
    df = pd.DataFrame(results)
    logger.info(f"\nTactical Allocation Comparison:")
    logger.info("\n" + df.to_string(index=False))
    
    return results


def demo_different_allocations():
    """
    演示4: 不同地区配置的效果对比
    
    对比集中美股的配置 vs 全球分散配置
    """
    logger.info("\n" + "=" * 60)
    logger.info("Demo 4: Regional Allocation Comparison")
    logger.info("=" * 60)
    
    # 获取数据
    data_source = YahooFinanceSource()
    symbols = ["VTI", "VGK", "VPL", "VWO", "BND", "BNDX", "TIP"]
    
    all_data = {}
    for symbol in symbols:
        try:
            df = data_source.get_data(symbol, period="5y")
            all_data[symbol] = df['close']
        except Exception as e:
            logger.warning(f"  Failed to load {symbol}: {e}")
    
    price_data = pd.DataFrame(all_data).fillna(method='ffill').dropna()
    
    allocations = [
        {
            "name": "US Heavy (Home Bias)",
            "us": 0.80, "europe": 0.10, "asia": 0.07, "emerging": 0.03,
        },
        {
            "name": "Balanced (Default)",
            "us": 0.60, "europe": 0.20, "asia": 0.15, "emerging": 0.05,
        },
        {
            "name": "Global Equal",
            "us": 0.40, "europe": 0.25, "asia": 0.25, "emerging": 0.10,
        },
        {
            "name": "Emerging Heavy",
            "us": 0.40, "europe": 0.20, "asia": 0.20, "emerging": 0.20,
        },
    ]
    
    results = []
    
    for alloc in allocations:
        strategy = GlobalMultiAssetStrategy(
            name=f"demo_{alloc['name'].replace(' ', '_').lower()}",
            equity_ratio=0.60,
            bond_ratio=0.40,
            us_weight=alloc["us"],
            europe_weight=alloc["europe"],
            asia_pacific_weight=alloc["asia"],
            emerging_weight=alloc["emerging"],
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
        )
        
        config = BacktestConfig(initial_cash=100000.0, commission_rate=0.001)
        engine = BacktestEngine(config)
        result = engine.run(strategy, price_data)
        
        results.append({
            "Allocation": alloc["name"],
            "US": f"{alloc['us']:.0%}",
            "Europe": f"{alloc['europe']:.0%}",
            "Asia": f"{alloc['asia']:.0%}",
            "EM": f"{alloc['emerging']:.0%}",
            "Return": f"{result.metrics.total_return:.2%}",
            "Sharpe": f"{result.metrics.sharpe_ratio:.2f}",
            "Max DD": f"{result.metrics.max_drawdown:.2%}",
        })
        
        logger.info(f"  {alloc['name']}: Return={result.metrics.total_return:.2%}, "
                   f"Sharpe={result.metrics.sharpe_ratio:.2f}")
    
    # 创建对比表
    df = pd.DataFrame(results)
    logger.info(f"\nRegional Allocation Comparison:")
    logger.info("\n" + df.to_string(index=False))
    
    return results


def demo_plot_allocation():
    """
    演示5: 可视化资产配置
    
    展示策略的目标配置和实际配置变化
    """
    logger.info("\n" + "=" * 60)
    logger.info("Demo 5: Allocation Visualization")
    logger.info("=" * 60)
    
    import matplotlib.pyplot as plt
    
    # 创建策略实例
    strategy = GlobalMultiAssetStrategy(
        name="demo_visualization",
        equity_ratio=0.60,
        bond_ratio=0.40,
        us_weight=0.60,
        europe_weight=0.20,
        asia_pacific_weight=0.15,
        emerging_weight=0.05,
        us_bond_weight=0.60,
        international_bond_weight=0.25,
        tips_weight=0.15,
    )
    
    # 获取目标配置
    target_weights = strategy.get_target_weights()
    
    # 准备绘图数据
    equity_weights = []
    equity_labels = []
    bond_weights = []
    bond_labels = []
    
    for region, weight in target_weights.items():
        if "equity" in region:
            equity_weights.append(weight)
            equity_labels.append(region.replace("_equity", "").title())
        else:
            bond_weights.append(weight)
            bond_labels.append(region.replace("_", " ").title())
    
    # 创建图表
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 股票配置饼图
    axes[0, 0].pie(
        equity_weights,
        labels=equity_labels,
        autopct="%1.1f%%",
        startangle=90,
        colors=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
    )
    axes[0, 0].set_title("Equity Allocation (60% of Portfolio)")
    
    # 债券配置饼图
    axes[0, 1].pie(
        bond_weights,
        labels=bond_labels,
        autopct="%1.1f%%",
        startangle=90,
        colors=["#9467bd", "#8c564b", "#e377c2"],
    )
    axes[0, 1].set_title("Bond Allocation (40% of Portfolio)")
    
    # 整体股债配置
    axes[1, 0].pie(
        [0.60, 0.40],
        labels=["Equity (60%)", "Bond (40%)"],
        autopct="%1.1f%%",
        startangle=90,
        colors=["#2E86AB", "#A23B72"],
    )
    axes[1, 0].set_title("Stock/Bond Allocation")
    
    # 详细配置条形图
    all_labels = []
    all_weights = []
    all_colors = []
    
    color_map = {
        "us_equity": "#1f77b4",
        "europe_equity": "#ff7f0e",
        "asia_pacific_equity": "#2ca02c",
        "emerging_equity": "#d62728",
        "us_bond": "#9467bd",
        "international_bond": "#8c564b",
        "tips": "#e377c2",
    }
    
    for region, weight in target_weights.items():
        all_labels.append(region.replace("_", " ").title())
        all_weights.append(weight * 100)
        all_colors.append(color_map.get(region, "gray"))
    
    axes[1, 1].barh(all_labels, all_weights, color=all_colors)
    axes[1, 1].set_xlabel("Weight (%)")
    axes[1, 1].set_title("Detailed Asset Allocation")
    axes[1, 1].set_xlim(0, max(all_weights) * 1.2)
    
    # 添加数值标签
    for i, (label, weight) in enumerate(zip(all_labels, all_weights)):
        axes[1, 1].text(weight + 0.5, i, f"{weight:.1f}%", va="center")
    
    plt.tight_layout()
    
    # 保存图表
    output_dir = Path("./results")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "allocation_visualization.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    logger.info(f"  Chart saved to {output_path}")
    
    plt.close()


def main():
    """主函数 - 运行所有演示"""
    logger.info("=" * 60)
    logger.info("Global Multi-Asset Strategy Demonstration")
    logger.info("=" * 60)
    
    try:
        # Demo 1: 基础策略
        demo_basic_strategy()
        
        # Demo 2: 再平衡触发方式对比
        demo_rebalance_triggers()
        
        # Demo 3: 战术资产配置
        demo_tactical_allocation()
        
        # Demo 4: 不同地区配置对比
        demo_different_allocations()
        
        # Demo 5: 可视化
        demo_plot_allocation()
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()
    
    logger.info("\n" + "=" * 60)
    logger.info("All demos completed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
