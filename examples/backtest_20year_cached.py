"""
OpenBB 20年回测 - 使用缓存和更长重试间隔

由于 Yahoo Finance 和 OpenBB 都可能限流，此版本使用：
1. 更长的重试间隔（30秒-2分钟）
2. 持久化缓存
3. 分批获取数据
"""

import sys
from pathlib import Path
import logging
import time
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import numpy as np

from alphaloop.data import YahooFinanceSource, DataCache
from alphaloop.strategies.global_multi_asset import (
    GlobalMultiAssetStrategy,
    RebalanceTrigger,
    TacticalMethod,
)
from alphaloop.strategies import BuyHoldStrategy
from alphaloop.backtest import BacktestEngine, BacktestConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_data_with_long_retry(symbols, start, end, max_retries=5):
    """使用长间隔重试获取数据"""
    cache = DataCache(cache_dir="~/.cache/alphaloop", ttl_hours=168)
    
    all_data = {}
    source = YahooFinanceSource(cache=cache)
    
    for i, symbol in enumerate(symbols):
        cache_key = f"{symbol}_{start}_{end}"
        
        # 检查缓存
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(f"[{i+1}/{len(symbols)}] Using cached data for {symbol}")
            all_data[symbol] = cached["close"]
            continue
        
        # 获取数据
        success = False
        for attempt in range(max_retries):
            try:
                logger.info(f"[{i+1}/{len(symbols)}] Fetching {symbol} (attempt {attempt + 1}/{max_retries})...")
                df = source.get_data(symbol, start=start, end=end)
                if not df.empty:
                    all_data[symbol] = df["close"]
                    cache.set(cache_key, df)
                    logger.info(f"  ✓ Got {len(df)} rows")
                    success = True
                    break
            except Exception as e:
                wait_time = min(30 * (attempt + 1), 120)  # 30s, 60s, 90s, 120s, 120s
                logger.warning(f"  ✗ Failed: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"  Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
        
        if not success:
            logger.error(f"  Failed to fetch {symbol} after {max_retries} attempts")
        
        # 每个 symbol 之间等待更长时间
        if i < len(symbols) - 1:
            time.sleep(5)
    
    if not all_data:
        logger.warning("No real data fetched, using synthetic data for demonstration...")
        # 生成模拟数据
        dates = pd.date_range(start, end, freq='B')  # 工作日
        np.random.seed(42)
        
        for symbol in symbols:
            # 根据资产类型设置不同参数
            if symbol in ["VTI"]:
                mu, sigma = 0.0004, 0.012  # 美股
            elif symbol in ["VGK", "VPL"]:
                mu, sigma = 0.0003, 0.013  # 发达市场
            elif symbol == "VWO":
                mu, sigma = 0.00035, 0.015  # 新兴市场
            else:
                mu, sigma = 0.0001, 0.004  # 债券
            
            returns = np.random.normal(mu, sigma, len(dates))
            prices = 100 * np.exp(np.cumsum(returns))
            all_data[symbol] = pd.Series(prices, index=dates)
    
    # 合并数据
    price_data = pd.DataFrame(all_data)
    price_data = price_data.ffill().dropna()
    
    return price_data


def main():
    print("\n" + "="*70)
    print("OpenStrategy - 20-Year Backtest with OpenBB/Yahoo Data")
    print("="*70)
    
    symbols = ["VTI", "VGK", "VPL", "VWO", "BND", "BNDX", "TIP"]
    
    # 获取数据（使用长重试间隔）
    logger.info("Fetching 20-year data (this may take 10-15 minutes due to rate limits)...")
    data = fetch_data_with_long_retry(
        symbols,
        start="2004-01-01",
        end="2024-12-31",
    )
    
    logger.info(f"Data loaded: {len(data)} days from {data.index[0].date()} to {data.index[-1].date()}")
    
    # 回测配置
    config = BacktestConfig(
        initial_cash=100000.0,
        commission_rate=0.001,
        slippage=0.001,
    )
    
    # 策略
    strategies = {
        "US_60_40_BuyHold": BuyHoldStrategy(
            symbols=["VTI", "BND"],
            weights=[0.6, 0.4],
            name="us_6040_bh",
        ),
        "Global_60_40_Threshold": GlobalMultiAssetStrategy(
            equity_ratio=0.60,
            bond_ratio=0.40,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            name="global_6040_t",
        ),
        "Global_60_40_Quarterly": GlobalMultiAssetStrategy(
            equity_ratio=0.60,
            bond_ratio=0.40,
            rebalance_trigger=RebalanceTrigger.CALENDAR,
            rebalance_frequency=90,
            name="global_6040_q",
        ),
        "Global_50_50_Threshold": GlobalMultiAssetStrategy(
            equity_ratio=0.50,
            bond_ratio=0.50,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            name="global_5050",
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
    
    # 结果对比
    print("\n" + "="*70)
    print("20-Year Backtest Results (2004-2024)")
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
    df.to_csv(output_dir / "backtest_20year_results.csv", index=False)
    
    print("\n" + "="*70)
    print(f"Results saved to: {output_dir / 'backtest_20year_results.csv'}")
    print("="*70)


if __name__ == "__main__":
    main()
