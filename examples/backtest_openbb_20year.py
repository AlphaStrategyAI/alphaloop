"""
OpenBB 数据源 20 年回测示例 (2004-2024)

使用 OpenBB 数据源获取 7 只全球 ETF 的 20 年历史数据，
运行 GlobalMultiAssetStrategy 策略回测。

资产列表:
- VTI (美股)
- VGK (欧股)
- VPL (亚太)
- VWO (新兴市场)
- BND (美债)
- BNDX (国际债券)
- TIP (通胀保值)

运行方式:
    python backtest_openbb_20year.py
    
    # 使用特定 OpenBB provider
    python backtest_openbb_20year.py --provider yfinance
    
    # 对比不同再平衡策略
    python backtest_openbb_20year.py --compare-rebalance
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import asdict

import pandas as pd
import numpy as np

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alphaloop import BacktestEngine, BacktestConfig
from alphaloop.data.cache import DataCache
from alphaloop.strategies import (
    BuyHoldStrategy,
    GlobalMultiAssetStrategy,
    RebalanceTrigger,
    TacticalMethod,
)

# 尝试导入 OpenBB 数据源
try:
    from alphaloop.data.openbb_source import OpenBBDataSource
    OPENBB_AVAILABLE = True
except ImportError:
    OPENBB_AVAILABLE = False
    logger.warning("OpenBB not installed, using Yahoo Finance fallback")


# 资产配置
ASSETS = {
    "us_equity": "VTI",           # Vanguard Total Stock Market (美股)
    "europe_equity": "VGK",       # Vanguard FTSE Europe (欧股)
    "asia_pacific_equity": "VPL", # Vanguard FTSE Pacific (亚太)
    "emerging_equity": "VWO",     # Vanguard FTSE Emerging Markets (新兴市场)
    "us_bond": "BND",             # Vanguard Total Bond Market (美债)
    "international_bond": "BNDX", # Vanguard Total International Bond (国际债券)
    "tips": "TIP",                # iShares TIPS Bond (通胀保值)
}


class OpenBB20YearBacktest:
    """
    OpenBB 数据源 20 年回测分析器
    
    执行 2004-2024 年的完整回测，支持多种再平衡策略对比。
    """
    
    def __init__(
        self,
        start_date: str = "2004-01-01",
        end_date: str = "2024-12-31",
        initial_capital: float = 100000.0,
        output_dir: str = "./results/openbb_20year",
        data_provider: Optional[str] = None,
        cache_dir: Optional[str] = None,
        enable_fallback: bool = True,
    ):
        """
        初始化回测分析器
        
        Args:
            start_date: 回测开始日期
            end_date: 回测结束日期
            initial_capital: 初始资金
            output_dir: 输出目录
            data_provider: OpenBB 数据供应商 (yfinance, fmp, polygon)
            cache_dir: 数据缓存目录
            enable_fallback: 启用 Yahoo Finance 降级
        """
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.data_provider = data_provider
        self.enable_fallback = enable_fallback
        
        # 初始化缓存
        if cache_dir:
            self.cache = DataCache(cache_dir=cache_dir, ttl_hours=168)  # 7天缓存
        else:
            self.cache = DataCache(ttl_hours=168)
        
        # 初始化数据源
        self._init_data_source()
        
        # 数据存储
        self.price_data: Optional[pd.DataFrame] = None
        self.results: Dict[str, Any] = {}
    
    def _init_data_source(self) -> None:
        """初始化数据源"""
        if OPENBB_AVAILABLE:
            self.data_source = OpenBBDataSource(
                cache=self.cache,
                provider=self.data_provider,
                enable_fallback=self.enable_fallback,
                retry_count=3,
                retry_delay=1.0,
            )
            status = self.data_source.get_status()
            logger.info(f"Data source initialized: {status}")
        else:
            # 使用 Yahoo Finance
            from alphaloop.data.yahoo import YahooFinanceSource
            self.data_source = YahooFinanceSource(cache=self.cache)
            logger.info("Using Yahoo Finance data source")
    
    def fetch_data(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        获取所有资产的历史数据
        
        Args:
            force_refresh: 强制刷新缓存
            
        Returns:
            价格数据 DataFrame
        """
        if force_refresh:
            self.cache.clear(memory_only=False)
            logger.info("Cache cleared for fresh data fetch")
        
        logger.info(f"Fetching data from {self.start_date} to {self.end_date}")
        logger.info(f"Assets: {list(ASSETS.values())}")
        
        # 检查数据源状态
        if hasattr(self.data_source, 'get_status'):
            status = self.data_source.get_status()
            logger.info(f"Data source status: available={status.get('available')}, "
                       f"fallback={status.get('using_fallback')}")
        
        all_data = {}
        symbols = list(ASSETS.values())
        
        for symbol in symbols:
            try:
                logger.info(f"Fetching {symbol}...")
                df = self.data_source.get_data(
                    symbol=symbol,
                    start=self.start_date,
                    end=self.end_date,
                )
                
                if not df.empty and 'close' in df.columns:
                    all_data[symbol] = df['close']
                    logger.info(f"  ✓ {symbol}: {len(df)} rows, "
                               f"{df['close'].iloc[0]:.2f} -> {df['close'].iloc[-1]:.2f}")
                else:
                    logger.warning(f"  ✗ {symbol}: No data available")
                    
            except Exception as e:
                logger.error(f"  ✗ {symbol}: Failed - {e}")
        
        if not all_data:
            logger.warning("No real data available, generating synthetic data for demonstration...")
            all_data = self._generate_synthetic_data()
            logger.info(f"Generated synthetic data for {len(all_data)} assets")
        
        # 合并数据
        self.price_data = pd.DataFrame(all_data)
        self.price_data.index = pd.to_datetime(self.price_data.index)
        
        # 数据处理
        logger.info("\nProcessing data...")
        
        # 前向填充缺失值
        self.price_data = self.price_data.ffill()
        
        # 删除全部为 NaN 的列
        self.price_data = self.price_data.dropna(axis=1, how='all')
        
        # 对齐起始日期 - 所有资产都有数据的第一日
        first_valid_idx = self.price_data.dropna().index[0]
        self.price_data = self.price_data.loc[first_valid_idx:]
        
        # 保存原始数据
        data_path = self.output_dir / "price_data.csv"
        self.price_data.to_csv(data_path)
        logger.info(f"Price data saved to: {data_path}")
        
        # 打印统计信息
        logger.info("\n" + "="*60)
        logger.info("Data Summary:")
        logger.info(f"  Date range: {self.price_data.index[0].date()} to {self.price_data.index[-1].date()}")
        logger.info(f"  Total days: {len(self.price_data)}")
        logger.info(f"  Assets: {len(self.price_data.columns)}")
        logger.info(f"  Columns: {list(self.price_data.columns)}")
        logger.info("="*60)
        
        return self.price_data
    
    def _generate_synthetic_data(self) -> Dict[str, pd.Series]:
        """
        生成基于历史统计的合成数据
        
        当真实数据不可用时，使用此方法来生成演示数据
        """
        logger.info("Generating synthetic market data based on historical statistics...")
        
        np.random.seed(42)
        dates = pd.date_range(self.start_date, self.end_date, freq='B')
        n_days = len(dates)
        
        # 资产参数 (年化收益, 年化波动率)
        asset_params = {
            "VTI": {"mu": 0.10, "sigma": 0.15},   # 美股
            "VGK": {"mu": 0.06, "sigma": 0.17},  # 欧股
            "VPL": {"mu": 0.06, "sigma": 0.16},  # 亚太
            "VWO": {"mu": 0.07, "sigma": 0.20},  # 新兴市场
            "BND": {"mu": 0.04, "sigma": 0.05},  # 美债
            "BNDX": {"mu": 0.03, "sigma": 0.07}, # 国际债券
            "TIP": {"mu": 0.035, "sigma": 0.06}, # 通胀保值
        }
        
        synthetic_data = {}
        
        for symbol in ASSETS.values():
            params = asset_params.get(symbol, {"mu": 0.05, "sigma": 0.15})
            
            # 计算日收益参数
            daily_mu = params["mu"] / 252
            daily_sigma = params["sigma"] / np.sqrt(252)
            
            # 生成随机收益
            returns = np.random.normal(daily_mu, daily_sigma, n_days)
            
            # 添加一些市场危机时期
            # 2008金融危机
            crisis_2008 = (dates >= "2008-09-01") & (dates <= "2009-03-31")
            if symbol in ["VTI", "VGK", "VPL", "VWO"]:
                returns[crisis_2008] -= 0.001  # 股票额外下跌
            elif symbol in ["BND", "TIP"]:
                returns[crisis_2008] += 0.0003  # 债券避险
            
            # 2020新冠危机
            crisis_2020 = (dates >= "2020-02-15") & (dates <= "2020-04-15")
            if symbol in ["VTI", "VGK", "VPL", "VWO"]:
                returns[crisis_2020] -= 0.002
            elif symbol in ["BND", "TIP"]:
                returns[crisis_2020] += 0.0005
            
            # 计算价格序列
            prices = 100 * np.exp(np.cumsum(returns))
            synthetic_data[symbol] = pd.Series(prices, index=dates)
            
            logger.info(f"  Generated {symbol}: {len(prices)} days, "
                       f"{prices[0]:.2f} -> {prices[-1]:.2f} "
                       f"({(prices[-1]/prices[0]-1)*100:.1f}%)")
        
        logger.info("Synthetic data generation complete")
        return synthetic_data
    
    def run_6040_benchmark(self) -> Dict[str, Any]:
        """运行 60/40 美股/美债基准策略"""
        logger.info("\n" + "="*60)
        logger.info("Running 60/40 US Benchmark Strategy")
        logger.info("="*60)
        
        config = BacktestConfig(
            initial_cash=self.initial_capital,
            commission_rate=0.001,
        )
        
        strategy = GlobalMultiAssetStrategy(
            equity_ratio=0.6,
            bond_ratio=0.4,
            us_weight=1.0,
            europe_weight=0.0,
            asia_pacific_weight=0.0,
            emerging_weight=0.0,
            us_bond_weight=1.0,
            international_bond_weight=0.0,
            tips_weight=0.0,
            rebalance_trigger=RebalanceTrigger.THRESHOLD,
            rebalance_threshold=0.05,
            tactical_method=TacticalMethod.NONE,
            name="60_40_us_benchmark",
        )
        
        engine = BacktestEngine(config)
        result = engine.run(strategy, self.price_data)
        
        logger.info(f"Total Return: {result.metrics.total_return:.2%}")
        logger.info(f"CAGR: {result.metrics.cagr:.2%}")
        logger.info(f"Sharpe: {result.metrics.sharpe_ratio:.2f}")
        logger.info(f"Max DD: {result.metrics.max_drawdown:.2%}")
        
        return {
            "name": "60/40 US Benchmark",
            "key": "60_40_us",
            "result": result,
            "strategy": strategy,
        }
    
    def run_global_equal_weight(self) -> Dict[str, Any]:
        """运行全球等权策略"""
        logger.info("\n" + "="*60)
        logger.info("Running Global Equal Weight Strategy")
        logger.info("="*60)
        
        config = BacktestConfig(
            initial_cash=self.initial_capital,
            commission_rate=0.001,
        )
        
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
            name="equal_weight",
        )
        
        engine = BacktestEngine(config)
        result = engine.run(strategy, self.price_data)
        
        logger.info(f"Total Return: {result.metrics.total_return:.2%}")
        logger.info(f"CAGR: {result.metrics.cagr:.2%}")
        logger.info(f"Sharpe: {result.metrics.sharpe_ratio:.2f}")
        logger.info(f"Max DD: {result.metrics.max_drawdown:.2%}")
        
        return {
            "name": "Global Equal Weight",
            "key": "equal_weight",
            "result": result,
            "strategy": strategy,
        }
    
    def run_buy_hold_vti(self) -> Dict[str, Any]:
        """运行 VTI 买入持有策略"""
        logger.info("\n" + "="*60)
        logger.info("Running Buy & Hold (VTI) Strategy")
        logger.info("="*60)
        
        config = BacktestConfig(
            initial_cash=self.initial_capital,
            commission_rate=0.001,
        )
        
        strategy = BuyHoldStrategy(
            symbols=["VTI"],
            weights=[1.0],
            name="buy_hold_vti",
        )
        
        engine = BacktestEngine(config)
        result = engine.run(strategy, self.price_data)
        
        logger.info(f"Total Return: {result.metrics.total_return:.2%}")
        logger.info(f"CAGR: {result.metrics.cagr:.2%}")
        logger.info(f"Sharpe: {result.metrics.sharpe_ratio:.2f}")
        logger.info(f"Max DD: {result.metrics.max_drawdown:.2%}")
        
        return {
            "name": "Buy & Hold (VTI)",
            "key": "buy_hold",
            "result": result,
            "strategy": strategy,
        }
    
    def run_global_multi_asset(self, rebalance_trigger: RebalanceTrigger = RebalanceTrigger.THRESHOLD) -> Dict[str, Any]:
        """
        运行全球多资产策略
        
        Args:
            rebalance_trigger: 再平衡触发方式
        """
        logger.info("\n" + "="*60)
        logger.info(f"Running Global Multi-Asset Strategy ({rebalance_trigger.value})")
        logger.info("="*60)
        
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
            rebalance_trigger=rebalance_trigger,
            rebalance_threshold=0.05,
            rebalance_frequency=30,
            tactical_method=TacticalMethod.NONE,
            name=f"global_multi_asset_{rebalance_trigger.value}",
        )
        
        engine = BacktestEngine(config)
        result = engine.run(strategy, self.price_data)
        
        logger.info(f"Total Return: {result.metrics.total_return:.2%}")
        logger.info(f"CAGR: {result.metrics.cagr:.2%}")
        logger.info(f"Sharpe: {result.metrics.sharpe_ratio:.2f}")
        logger.info(f"Max DD: {result.metrics.max_drawdown:.2%}")
        logger.info(f"Trades: {len(result.trades)}")
        
        return {
            "name": f"Global Multi-Asset ({rebalance_trigger.value})",
            "key": f"global_multi_asset_{rebalance_trigger.value}",
            "result": result,
            "strategy": strategy,
        }
    
    def run_tactical_momentum(self) -> Dict[str, Any]:
        """运行带动量战术配置的策略"""
        logger.info("\n" + "="*60)
        logger.info("Running Tactical Momentum Strategy")
        logger.info("="*60)
        
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
            name="tactical_momentum",
        )
        
        engine = BacktestEngine(config)
        result = engine.run(strategy, self.price_data)
        
        logger.info(f"Total Return: {result.metrics.total_return:.2%}")
        logger.info(f"CAGR: {result.metrics.cagr:.2%}")
        logger.info(f"Sharpe: {result.metrics.sharpe_ratio:.2f}")
        logger.info(f"Max DD: {result.metrics.max_drawdown:.2%}")
        
        return {
            "name": "Tactical Momentum",
            "key": "tactical_momentum",
            "result": result,
            "strategy": strategy,
        }
    
    def run_tactical_volatility(self) -> Dict[str, Any]:
        """运行带波动率战术配置的策略"""
        logger.info("\n" + "="*60)
        logger.info("Running Tactical Volatility Strategy")
        logger.info("="*60)
        
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
            tactical_method=TacticalMethod.VOLATILITY,
            lookback_days=60,
            volatility_target=0.10,
            name="tactical_volatility",
        )
        
        engine = BacktestEngine(config)
        result = engine.run(strategy, self.price_data)
        
        logger.info(f"Total Return: {result.metrics.total_return:.2%}")
        logger.info(f"CAGR: {result.metrics.cagr:.2%}")
        logger.info(f"Sharpe: {result.metrics.sharpe_ratio:.2f}")
        logger.info(f"Max DD: {result.metrics.max_drawdown:.2%}")
        
        return {
            "name": "Tactical Volatility",
            "key": "tactical_volatility",
            "result": result,
            "strategy": strategy,
        }
    
    def compare_rebalance_strategies(self) -> Dict[str, Any]:
        """对比不同再平衡策略"""
        logger.info("\n" + "="*60)
        logger.info("Comparing Rebalance Strategies")
        logger.info("="*60)
        
        results = {}
        
        # 阈值触发
        results['threshold'] = self.run_global_multi_asset(RebalanceTrigger.THRESHOLD)
        
        # 日历触发 (月度)
        results['calendar'] = self.run_global_multi_asset(RebalanceTrigger.CALENDAR)
        
        # 两者结合
        results['both'] = self.run_global_multi_asset(RebalanceTrigger.BOTH)
        
        return results
    
    def run_all_strategies(self, compare_rebalance: bool = False) -> Dict[str, Any]:
        """
        运行所有策略
        
        Args:
            compare_rebalance: 是否对比再平衡策略
            
        Returns:
            所有策略结果字典
        """
        if self.price_data is None:
            self.fetch_data()
        
        self.results = {}
        
        # 基准策略
        self.results["60_40_us"] = self.run_6040_benchmark()
        self.results["equal_weight"] = self.run_global_equal_weight()
        self.results["buy_hold"] = self.run_buy_hold_vti()
        
        # 主要策略
        self.results["global_multi_asset"] = self.run_global_multi_asset()
        
        # 战术配置策略
        self.results["tactical_momentum"] = self.run_tactical_momentum()
        self.results["tactical_volatility"] = self.run_tactical_volatility()
        
        # 对比再平衡策略
        if compare_rebalance:
            rebalance_results = self.compare_rebalance_strategies()
            self.results.update(rebalance_results)
        
        return self.results
    
    def generate_report(self) -> Dict[str, Any]:
        """
        生成回测报告
        
        Returns:
            报告数据字典
        """
        logger.info("\n" + "="*60)
        logger.info("Generating Report")
        logger.info("="*60)
        
        # 构建报告
        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "start_date": self.start_date,
                "end_date": self.end_date,
                "initial_capital": self.initial_capital,
                "data_source": "OpenBB" if OPENBB_AVAILABLE else "Yahoo Finance",
                "provider": self.data_provider,
            },
            "assets": ASSETS,
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
                "n_trades": len(result.trades),
                "final_value": float(result.history["total_value"].iloc[-1]),
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
        
        # 打印对比表
        logger.info("\nStrategy Comparison:")
        print("\n" + comparison_df.to_string(index=False))
        
        # 保存 JSON 报告
        json_path = self.output_dir / "openbb_backtest_report.json"
        with open(json_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"\nJSON report saved to: {json_path}")
        
        # 保存 CSV 对比表
        csv_path = self.output_dir / "strategy_comparison.csv"
        comparison_df.to_csv(csv_path, index=False)
        logger.info(f"CSV comparison saved to: {csv_path}")
        
        return report
    
    def run_full_analysis(self, compare_rebalance: bool = False) -> None:
        """
        运行完整分析
        
        Args:
            compare_rebalance: 是否对比再平衡策略
        """
        logger.info("="*60)
        logger.info("OpenStrategy - OpenBB 20-Year Backtest (2004-2024)")
        logger.info("="*60)
        
        start_time = datetime.now()
        
        # 1. 获取数据
        self.fetch_data()
        
        # 2. 运行所有策略
        self.run_all_strategies(compare_rebalance=compare_rebalance)
        
        # 3. 生成报告
        self.generate_report()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("\n" + "="*60)
        logger.info("Analysis Complete!")
        logger.info(f"Duration: {duration:.1f} seconds")
        logger.info(f"Results saved to: {self.output_dir.absolute()}")
        logger.info("="*60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="OpenStrategy OpenBB 20-Year Backtest"
    )
    parser.add_argument(
        "--start", 
        default="2004-01-01",
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", 
        default="2024-12-31",
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--capital", 
        type=float, 
        default=100000.0,
        help="Initial capital"
    )
    parser.add_argument(
        "--output", 
        default="./results/openbb_20year",
        help="Output directory"
    )
    parser.add_argument(
        "--provider",
        choices=["yfinance", "fmp", "polygon", "alpha_vantage"],
        help="OpenBB data provider"
    )
    parser.add_argument(
        "--cache-dir",
        default="~/.cache/alphaloop/openbb",
        help="Cache directory"
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable Yahoo Finance fallback"
    )
    parser.add_argument(
        "--compare-rebalance",
        action="store_true",
        help="Compare different rebalance strategies"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force refresh data cache"
    )
    
    args = parser.parse_args()
    
    # 创建回测实例
    backtest = OpenBB20YearBacktest(
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        output_dir=args.output,
        data_provider=args.provider,
        cache_dir=args.cache_dir,
        enable_fallback=not args.no_fallback,
    )
    
    # 获取数据 (如有需要则刷新)
    if args.refresh:
        backtest.fetch_data(force_refresh=True)
    
    # 运行完整分析
    backtest.run_full_analysis(compare_rebalance=args.compare_rebalance)


if __name__ == "__main__":
    main()
