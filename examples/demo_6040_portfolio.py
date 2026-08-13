"""
OpenStrategy v2 示例 - 60/40 股债组合回测

60% 股票 (VTI) + 40% 债券 (BND) 的经典配置
对比买入持有 vs 定期再平衡策略
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alphaloop.data import YahooFinanceSource
from alphaloop.strategies import BuyHoldStrategy, RebalanceStrategy
from alphaloop.core.enums import RebalanceMethod
from alphaloop.backtest import BacktestEngine, BacktestConfig
from alphaloop.backtest.report import BacktestReport


def main():
    print("=" * 60)
    print("OpenStrategy v2 - 60/40 Portfolio Backtest Demo")
    print("=" * 60)
    
    # 1. 配置
    symbols = ["VTI", "BND"]  # 全股市ETF + 总债券ETF
    weights = [0.6, 0.4]
    
    # 2. 获取数据
    print("\n📊 Fetching data...")
    source = YahooFinanceSource()
    data = source.get_prices(symbols, period="3y")
    print(f"   Data: {len(data)} days from {data.index[0].date()} to {data.index[-1].date()}")
    
    # 3. 策略1: 买入持有
    print("\n📈 Running Buy & Hold Strategy...")
    bh_strategy = BuyHoldStrategy(
        symbols=symbols,
        weights=weights,
        initial_investment=100000.0,
    )
    
    config = BacktestConfig(
        initial_cash=100000.0,
        commission_rate=0.001,  # 0.1% 佣金
    )
    
    engine = BacktestEngine(config)
    bh_result = engine.run(bh_strategy, data)
    
    print(f"   Total Return: {bh_result.metrics.total_return:.2%}")
    print(f"   Sharpe Ratio: {bh_result.metrics.sharpe_ratio:.2f}")
    print(f"   Max Drawdown: {bh_result.metrics.max_drawdown:.2%}")
    
    # 4. 策略2: 定期再平衡（每季度）
    print("\n🔄 Running Quarterly Rebalance Strategy...")
    reb_strategy = RebalanceStrategy(
        symbols=symbols,
        weights=weights,
        method=RebalanceMethod.CALENDAR,
        frequency_days=90,  # 每90天
    )
    
    reb_result = engine.run(reb_strategy, data)
    
    print(f"   Total Return: {reb_result.metrics.total_return:.2%}")
    print(f"   Sharpe Ratio: {reb_result.metrics.sharpe_ratio:.2f}")
    print(f"   Max Drawdown: {reb_result.metrics.max_drawdown:.2%}")
    print(f"   # of Rebalances: {len(reb_result.trades) // 2}")  # 每次再平衡包含买卖
    
    # 5. 策略3: 阈值再平衡（偏离5%时）
    print("\n⚡ Running Threshold Rebalance Strategy...")
    th_strategy = RebalanceStrategy(
        symbols=symbols,
        weights=weights,
        method=RebalanceMethod.THRESHOLD,
        threshold=0.05,  # 5% 阈值
    )
    
    th_result = engine.run(th_strategy, data)
    
    print(f"   Total Return: {th_result.metrics.total_return:.2%}")
    print(f"   Sharpe Ratio: {th_result.metrics.sharpe_ratio:.2f}")
    print(f"   Max Drawdown: {th_result.metrics.max_drawdown:.2%}")
    print(f"   # of Rebalances: {len(th_result.trades) // 2}")
    
    # 6. 对比总结
    print("\n" + "=" * 60)
    print("Comparison Summary")
    print("=" * 60)
    print(f"{'Strategy':<20} {'Return':>10} {'Sharpe':>8} {'Max DD':>10} {'Trades':>8}")
    print("-" * 60)
    
    results = [
        ("Buy & Hold", bh_result),
        ("Quarterly Rebal", reb_result),
        ("Threshold Rebal", th_result),
    ]
    
    for name, result in results:
        print(f"{name:<20} {result.metrics.total_return:>9.2%} {result.metrics.sharpe_ratio:>8.2f} "
              f"{result.metrics.max_drawdown:>9.2%} {len(result.trades):>8}")
    
    # 7. 保存报告
    print("\n💾 Saving reports...")
    report_dir = Path(__file__).parent / "reports"
    report_dir.mkdir(exist_ok=True)
    
    for name, result in results:
        report = BacktestReport(result)
        filename = name.lower().replace(" & ", "_").replace(" ", "_")
        report.to_html(report_dir / f"{filename}_report.html")
        report.to_json(report_dir / f"{filename}_report.json")
    
    print(f"   Reports saved to: {report_dir}")
    print("\n✅ Demo completed!")


if __name__ == "__main__":
    main()
