# OpenStrategy

> *Time in the market beats timing the market.*

开源量化投资策略框架 - 简单、可靠、适合普通投资者

---

## The Problem

**Most investors fail not because of bad markets, but because of bad behavior.**

- Chasing last year's winners
- Panic selling at market bottoms
- Overtrading and eroding returns with fees
- Trying to predict the unpredictable

The financial industry sells complexity—stock picking, market timing, and constant trading. Yet the evidence consistently shows that simple, disciplined strategies outperform complex ones over time.

**OpenStrategy offers a different path.**

---

## Investment Philosophy

### 1. Asset Allocation is King

The single most important investment decision isn't *what* to buy, but *how much* of each asset class.

Studies show that **90%+ of portfolio variance** comes from asset allocation, not security selection. A well-diversified basket of index funds, properly allocated, will beat most professional stock pickers over the long run.

**The Insight**: Don't try to pick winners. Own the entire market.

### 2. Diversification is the Only Free Lunch

Harry Markowitz's Nobel Prize-winning work demonstrated that combining uncorrelated assets can reduce risk without sacrificing expected returns.

- Equities and bonds often move in opposite directions during crises
- Geographic diversification protects against country-specific risks
- Multiple asset classes smooth the journey

**The Insight**: Don't put all your eggs in one basket—or even in baskets on the same table.

### 3. Discipline Beats Emotion

The greatest destroyer of wealth isn't market volatility—it's investor behavior.

- Fear makes us sell at market bottoms
- Greed makes us buy at market tops
- Overconfidence leads to excessive trading
- Regret causes us to hold losers too long

Systematic rebalancing removes emotion from the equation, mechanically enforcing **"buy low, sell high"** through disciplined portfolio maintenance.

**The Insight**: Set rules. Follow them. Ignore the noise.

### 4. Time in Market Beats Timing the Market

Compounding requires time. Time requires staying invested through volatility.

Markets will crash. They always do. But over decades, they have consistently rewarded patient investors. The investors who panic and sell during downturns lock in temporary losses as permanent ones.

**The Insight**: Patience isn't just a virtue. It's the strategy.

---

## Features

- **分层架构**: 清晰的数据层、策略层、回测层、分析层分离
- **多数据源**: 支持 Yahoo Finance (全球)、AKShare (A股)、CCXT (加密货币)
- **策略插件**: 基于工厂模式的策略注册机制
- **完整回测**: 交易成本、滑点、绩效指标计算
- **风险分析**: VaR、CVaR、Beta、蒙特卡洛模拟
- **零代码构建器**: 拖拽式策略积木系统，20+预设策略模板
- **模拟盘交易**: 真实市场环境测试策略，支持自动运行
- **通知系统**: 支持邮件、Telegram、企业微信多渠道通知
- **排行榜**: 用户收益排行，策略表现对比
- **成就系统**: 投资成就徽章，激励持续学习
- **教育内容**: 10篇策略科普文章，交互式投资课程
- **简单易用**: 几行代码即可运行回测

---

## Quick Start

### Installation

```bash
pip install openstrategy
```

### Example: Buy & Hold Strategy

```python
from openstrategy import (
    YahooFinanceSource,
    BuyHoldStrategy,
    BacktestEngine,
    BacktestConfig,
)

# 1. Fetch data
source = YahooFinanceSource()
data = source.get_prices(
    ["VTI", "BND", "VXUS"],  # US Stocks, Bonds, International
    period="5y"
)

# 2. Create strategy
strategy = BuyHoldStrategy(
    symbols=["VTI", "BND", "VXUS"],
    weights=[0.6, 0.3, 0.1],  # 60/30/10 allocation
)

# 3. Run backtest
config = BacktestConfig(
    initial_cash=100000.0,
    commission_rate=0.001,
)
engine = BacktestEngine(config)
result = engine.run(strategy, data)

# 4. View results
print(f"Total Return: {result.metrics.total_return:.2%}")
print(f"Sharpe Ratio: {result.metrics.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.metrics.max_drawdown:.2%}")
```

### Example: Rebalancing Strategy

```python
from openstrategy import RebalanceStrategy
from openstrategy.core.enums import RebalanceMethod

# Threshold-based rebalancing (triggered at 5% drift)
strategy = RebalanceStrategy(
    symbols=["VTI", "BND", "VXUS"],
    weights=[0.6, 0.3, 0.1],
    method=RebalanceMethod.THRESHOLD,
    threshold=0.05,
)

# Or calendar-based rebalancing (every 30 days)
strategy = RebalanceStrategy(
    symbols=["VTI", "BND", "VXUS"],
    weights=[0.6, 0.3, 0.1],
    method=RebalanceMethod.CALENDAR,
    frequency_days=30,
)
```

### Example: China A-Share Data

```python
from openstrategy import AKShareSource

source = AKShareSource()
df = source.get_data("600519")  # Kweichow Moutai
print(df.tail())
```

---

## CLI Commands

```bash
# Run backtest
openstrategy backtest --config strategy.yaml --output ./results

# Fetch data
openstrategy fetch --symbol AAPL --source yahoo --output data.csv

# Optimize parameters
openstrategy optimize --config strategy.yaml --method bayesian
```

---

## Project Architecture

```
openstrategy/
├── core/           # Domain models (Portfolio, Asset, Position)
├── data/           # Data layer (Yahoo, AKShare, CCXT)
├── strategies/     # Strategy layer (BuyHold, Rebalance)
├── backtest/       # Backtesting layer (Engine, Broker, Metrics)
├── analysis/       # Analysis layer (Risk, MonteCarlo)
└── cli/            # Command line interface
```

---

## Supported Strategies

- **BuyHoldStrategy**: Buy and hold (passive benchmark)
- **RebalanceStrategy**: Asset allocation rebalancing
  - Threshold trigger
  - Calendar trigger
  - Combined trigger

---

## Backtest Metrics

- Total Return
- CAGR (Compound Annual Growth Rate)
- Sharpe Ratio
- Sortino Ratio
- Max Drawdown
- Calmar Ratio
- Volatility

---

## Risk Analysis

```python
from openstrategy.analysis import calculate_var, MonteCarloSimulation

# VaR calculation
var_95 = calculate_var(returns, confidence=0.95)
print(f"95% VaR: {var_95:.2%}")

# Monte Carlo simulation
mc = MonteCarloSimulation(historical_returns, weights=[0.6, 0.3, 0.1])
result = mc.simulate(n_sims=10000, years=10)
print(f"Median value in 10 years: ${result.median_final_value:,.2f}")
print(f"Probability of profit: {result.probability_of_profit:.2%}")
```

---

## Development

```bash
# Clone repository
git clone https://github.com/fpc0000/openstrategy.git
cd openstrategy

# Install development dependencies
pip install -e ".[dev,all]"

# Run tests
pytest

# Code formatting
black src/
ruff check src/
```

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Disclaimer

> **Investing involves risk, including possible loss of principal.**
>
> This project is for educational purposes only and does not constitute investment advice. Past performance does not guarantee future results. Consult a qualified financial advisor before making investment decisions.

---

**Built for the patient. Powered by principles. Open to everyone.**

*"The stock market is a device for transferring money from the impatient to the patient."*  
— Warren Buffett

---

**The best time to start investing was 20 years ago. The second best time is now.**
