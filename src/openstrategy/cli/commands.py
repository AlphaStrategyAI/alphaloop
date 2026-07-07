"""
CLI 命令实现
"""

import json
import logging
from pathlib import Path

import yaml

from ..backtest import BacktestConfig, BacktestEngine
from ..data import AKShareSource, YahooFinanceSource
from ..strategies import StrategyFactory

logger = logging.getLogger(__name__)


def _build_source(name: str, **kwargs):
    """Map CLI source name → DataSource instance.

    Lazy-imports optional data sources so users without akshare/ccxt/openbb
    installed don't see an ImportError just from constructing the CLI.
    """
    if name == "yahoo":
        return YahooFinanceSource()
    if name == "akshare":
        return AKShareSource()
    if name == "ccxt":
        from ..data.ccxt import CCXTSource

        return CCXTSource(
            exchange=kwargs.get("exchange", "okx"),
            use_proxy=False,  # public market data — no proxy by default
        )
    if name == "openbb":
        from ..data.openbb_source import OpenBBDataSource

        return OpenBBDataSource(enable_fallback=True)
    raise ValueError(f"不支持的数据源: {name}")


def run_backtest(args):
    """运行回测命令"""
    print(f"运行回测: {args.config}")

    # 加载配置
    config_path = Path(args.config)
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # 获取数据
    symbols = config.get("symbols", [])
    start = args.start or config.get("start")
    end = args.end or config.get("end")

    print(f"获取数据: {symbols}")
    source = YahooFinanceSource()
    data = source.get_prices(symbols, start=start, end=end)

    # 创建策略
    strategy_config = config.get("strategy", {})
    strategy_type = strategy_config.get("type", "buy_hold")
    strategy = StrategyFactory.create(
        strategy_type, symbols=symbols, **strategy_config.get("params", {})
    )

    # 运行回测
    backtest_config = BacktestConfig(
        initial_cash=config.get("initial_cash", 100000.0),
        commission_rate=config.get("commission_rate", 0.001),
    )

    engine = BacktestEngine(backtest_config)
    result = engine.run(strategy, data)

    # 输出结果
    print("\n" + "=" * 50)
    print("回测结果")
    print("=" * 50)
    print(f"总收益率: {result.metrics.total_return:.2%}")
    print(f"年化收益率: {result.metrics.cagr:.2%}")
    print(f"夏普比率: {result.metrics.sharpe_ratio:.2f}")
    print(f"最大回撤: {result.metrics.max_drawdown:.2%}")
    print(f"交易次数: {len(result.trades)}")

    # 保存报告
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        from ..backtest.report import BacktestReport

        report = BacktestReport(result)
        report.to_json(output_dir / "report.json")
        report.to_html(output_dir / "report.html")
        print(f"\n报告已保存到: {output_dir}")

    return 0


def optimize_strategy(args):
    """参数优化命令"""
    print(f"参数优化: {args.config}")
    print(f"方法: {args.method}, 最大评估: {args.max_eval}")

    # TODO: 实现参数优化
    print("参数优化功能开发中...")
    return 0


def fetch_data(args):
    """获取数据命令"""
    print(f"获取数据: {args.symbol} from {args.source}")

    # 选择数据源
    source = _build_source(args.source, exchange=getattr(args, "exchange", "okx"))

    # 获取数据 (period 与 start/end 二选一)
    kwargs = {}
    if getattr(args, "period", None):
        kwargs["period"] = args.period

    df = source.get_data(args.symbol, start=args.start, end=args.end, **kwargs)

    print(f"获取到 {len(df)} 条数据 (日期范围: {df.index.min()} → {df.index.max()})")
    if not df.empty:
        # 避免在巨大表上 dump 全部行
        preview = df.tail().to_string()
        print(preview)

    # 保存数据 (.csv 或 .json 按后缀决定)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        suffix = output_path.suffix.lower()
        if suffix == ".json":
            payload = {
                "symbol": args.symbol,
                "source": args.source,
                "rows": len(df),
                "start": str(df.index.min()) if not df.empty else None,
                "end": str(df.index.max()) if not df.empty else None,
                "data": json.loads(df.reset_index().to_json(orient="records", date_format="iso")),
            }
            output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            df.to_csv(output_path)
        print(f"\n数据已保存到: {output_path}")

    return 0