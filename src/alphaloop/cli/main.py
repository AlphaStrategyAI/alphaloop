"""
CLI 主入口
"""

import argparse
import sys

from .commands import fetch_data, optimize_strategy, run_backtest
from .report import register as register_report


def create_parser() -> argparse.ArgumentParser:
    """创建命令行解析器"""
    parser = argparse.ArgumentParser(
        prog="alphaloop",
        description="OpenStrategy - 开源量化投资策略框架",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # backtest 命令
    backtest_parser = subparsers.add_parser("backtest", help="运行回测")
    backtest_parser.add_argument("--config", "-c", required=True, help="配置文件路径")
    backtest_parser.add_argument("--start", "-s", help="开始日期 (YYYY-MM-DD)")
    backtest_parser.add_argument("--end", "-e", help="结束日期 (YYYY-MM-DD)")
    backtest_parser.add_argument("--output", "-o", help="输出目录")

    # optimize 命令
    optimize_parser = subparsers.add_parser("optimize", help="参数优化")
    optimize_parser.add_argument("--config", "-c", required=True, help="配置文件路径")
    optimize_parser.add_argument(
        "--method", "-m", default="grid", choices=["grid", "bayesian"], help="优化方法"
    )
    optimize_parser.add_argument("--max-eval", type=int, default=100, help="最大评估次数")

    # fetch 命令
    fetch_parser = subparsers.add_parser("fetch", help="获取数据")
    fetch_parser.add_argument("--symbol", required=True, help="资产代码")
    fetch_parser.add_argument(
        "--source",
        default="yahoo",
        choices=["yahoo", "akshare", "ccxt", "openbb"],
        help="数据源",
    )
    fetch_parser.add_argument(
        "--exchange",
        default="okx",
        help="CCXT 交易所 (okx, binance, coinbase, ...)",
    )
    fetch_parser.add_argument(
        "--period", help="简写周期 (1d, 5d, 1mo, 3mo, 1y, 2y, 5y, 10y, ytd, max)"
    )
    fetch_parser.add_argument("--start", help="开始日期 (YYYY-MM-DD)")
    fetch_parser.add_argument("--end", help="结束日期 (YYYY-MM-DD)")
    fetch_parser.add_argument(
        "--output", "-o", help="输出文件路径 (.csv 或 .json，按后缀决定)"
    )

    # report 命令 (v1.0 acceptance report)
    register_report(subparsers)

    return parser


def main(args=None):
    """主入口函数"""
    parser = create_parser()
    args = parser.parse_args(args)

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "backtest":
            return run_backtest(args)
        elif args.command == "optimize":
            return optimize_strategy(args)
        elif args.command == "fetch":
            return fetch_data(args)
        elif args.command == "report":
            return args.func(args)
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"错误: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
