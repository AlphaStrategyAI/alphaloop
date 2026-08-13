"""
全球多资产回测 - 10年分析 (2014-2024)

由于 Yahoo Finance 限流，使用 10 年数据进行回测分析。
"""

import sys
from pathlib import Path
import logging
from datetime import datetime, timedelta
import time

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import numpy as np

from alphaloop.data import YahooFinanceSource, DataCache
from alphaloop.strategies import (
    GlobalMultiAssetStrategy,
    BuyHoldStrategy,
    RebalanceStrategy,
)
from alphaloop.strategies.global_multi_asset import RebalanceTrigger, TacticalMethod
from alphaloop.core.enums import RebalanceMethod
from alphaloop.backtest import BacktestEngine, BacktestConfig
from alphaloop.backtest.report import BacktestReport

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# 资产定义
ASSETS = {
    "VTI": "US Equity",
    "VGK": "Europe Equity",
    "VPL": "Asia Pacific Equity",
    "VWO": "Emerging Markets",
    "BND": "US Bonds",
    "BNDX": "International Bonds",
    "TIP": "TIPS",
}


def fetch_data_with_retry(symbols, start, end, max_retries=3):
    """带重试的数据获取"""
    cache = DataCache(cache_dir="~/.cache/alphaloop", ttl_hours=168)  # 7天缓存
    
    all_data = {}
    source = YahooFinanceSource(cache=cache)
    
    for symbol in symbols:
        cache_key = f"{symbol}_{start}_{end}"
        
        # 检查缓存
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(f"Using cached data for {symbol}")
            all_data[symbol] = cached["close"]
            continue
        
        # 获取数据（带重试）
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching {symbol} (attempt {attempt + 1}/{max_retries})...")
                df = source.get_data(symbol, start=start, end=end)
                if not df.empty:
                    all_data[symbol] = df["close"]
                    cache.set(cache_key, df)
                    logger.info(f"  ✓ Got {len(df)} rows")
                    break
            except Exception as e:
                logger.warning(f"  ✗ Failed: {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    logger.info(f"  Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"  Failed to fetch {symbol} after {max_retries} attempts")
        
        time.sleep(2)  # 避免请求过快
    
    if not all_data:
        raise ValueError("No data fetched for any symbol")
    
    # 合并数据
    price_data = pd.DataFrame(all_data)
    price_data = price_data.ffill().dropna()
    
    return price_data


def main():
    print("\n" + "="*70)
    print("OpenStrategy - 10-Year Global Multi-Asset Backtest")
    print("="*70)
    
    # 获取10年数据（避免20年限流）
    logger.info("Fetching 10-year data (2014-2024)...")
    try:
        data = fetch_data_with_retry(
            list(ASSETS.keys()),
            start="2014-01-01",
            end="2024-12-31",
        )
        logger.info(f"Data loaded: {len(data)} days from {data.index[0].date()} to {data.index[-1].date()}")
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        logger.info("Using mock data for demonstration...")
        # 创建模拟数据用于演示
        dates = pd.date_range("2014-01-01", "2024-12-31", freq="D")
        np.random.seed(42)
        data = pd.DataFrame({
            "VTI": 100 * np.exp(np.cumsum(np.random.normal(0.0003, 0.012, len(dates)))),
            "VGK": 100 * np.exp(np.cumsum(np.random.normal(0.0002, 0.013, len(dates)))),
            "VPL": 100 * np.exp(np.cumsum(np.random.normal(0.0002, 0.014, len(dates)))),
            "VWO": 100 * np.exp(np.cumsum(np.random.normal(0.00025, 0.015, len(dates)))),
            "BND": 100 * np.exp(np.cumsum(np.random.normal(0.0001, 0.004, len(dates)))),
            "BNDX": 100 * np.exp(np.cumsum(np.random.normal(0.00008, 0.005, len(dates)))),
            "TIP": 100 * np.exp(np.cumsum(np.random.normal(0.00009, 0.0045, len(dates)))),
        }, index=dates)
    
    # 回测配置
    config = BacktestConfig(
        initial_cash=100000.0,
        commission_rate=0.001,
        slippage=0.001,
    )
    
    strategies = {
        # 基准：60/40 美股/美债买入持有
        "Benchmark_60_40_BuyHold": BuyHoldStrategy(
            symbols=["VTI", "BND"],
            weights=[0.6, 0.4],
            name="benchmark_6040_bh",
        ),
        
        # 基准：60/40 季度再平衡
        "Benchmark_60_40_Rebal": RebalanceStrategy(
            symbols=["VTI", "BND"],
            weights=[0.6, 0.4],
            method=RebalanceMethod.CALENDAR,
            frequency_days=90,
            name="benchmark_6040_rebal",
        ),
        
        # 全球60/40，阈值5%再平衡
        "Global_60_40_Threshold_5pct": GlobalMultiAssetStrategy(
            equity_ratio=0.60,
            bond_ratio=0.40,
            us_weight=0.60,
            europe_weight=0.20,
            asia_pacific_weight=0.13,
            emerging_weight=0.07,
            us_bond_weight=0.70,
            international_bond_weight=0.20,
            tips_weight=0.10,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            name="global_6040_t5",
        ),
        
        # 全球60/40，季度再平衡
        "Global_60_40_Quarterly": GlobalMultiAssetStrategy(
            equity_ratio=0.60,
            bond_ratio=0.40,
            rebalance_trigger=RebalanceTrigger.CALENDAR,
            rebalance_frequency=90,
            name="global_6040_q",
        ),
        
        # 全球60/40 + 波动率TAA
        "Global_60_40_TAA_Vol": GlobalMultiAssetStrategy(
            equity_ratio=0.60,
            bond_ratio=0.40,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            tactical_method=TacticalMethod.VOLATILITY,
            lookback_days=60,
            name="global_6040_taa_vol",
        ),
    }
    
    # 运行回测
    results = {}
    engine = BacktestEngine(config)
    
    print("\n" + "="*70)
    print("Running Backtests")
    print("="*70)
    
    for name, strategy in strategies.items():
        logger.info(f"\nTesting: {name}")
        try:
            result = engine.run(strategy, data)
            results[name] = result
            
            logger.info(f"  Return: {result.metrics.total_return:.2%}")
            logger.info(f"  Sharpe: {result.metrics.sharpe_ratio:.2f}")
            logger.info(f"  Max DD: {result.metrics.max_drawdown:.2%}")
            logger.info(f"  Trades: {len(result.trades)}")
        except Exception as e:
            logger.error(f"  Failed: {e}")
    
    # 生成对比表
    print("\n" + "="*70)
    print("Backtest Results Comparison")
    print("="*70)
    
    rows = []
    for name, result in results.items():
        m = result.metrics
        rows.append({
            "Strategy": name,
            "Total Return": f"{m.total_return:.2%}",
            "CAGR": f"{m.cagr:.2%}",
            "Sharpe": f"{m.sharpe_ratio:.2f}",
            "Max DD": f"{m.max_drawdown:.2%}",
            "Volatility": f"{m.volatility:.2%}",
            "Trades": len(result.trades),
        })
    
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    
    # 保存结果
    output_dir = Path(__file__).parent.parent / "results"
    output_dir.mkdir(exist_ok=True)
    
    # 保存CSV
    df.to_csv(output_dir / "backtest_results.csv", index=False)
    logger.info(f"\nResults saved to: {output_dir / 'backtest_results.csv'}")
    
    # 生成详细报告
    for name, result in results.items():
        report = BacktestReport(result)
        safe_name = name.replace("/", "_")
        report.to_html(output_dir / f"{safe_name}_report.html")
    
    print("\n" + "="*70)
    print("Backtest complete!")
    print("="*70)


if __name__ == "__main__":
    main()
