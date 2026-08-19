"""
CLI 主入口
"""

import argparse
import sys

from alphaloop.calibration.cli import register_judge_subcommand

from .commands import fetch_data, optimize_strategy, run_backtest
from .export import register as register_export
from .jobs import register as register_jobs
from .report import register as register_report


def _register_loop(subparsers: argparse._SubParsersAction) -> None:
    """Register the v0.7 ``loop`` subcommand (hybrid DAG orchestrator).

    Mirrors design doc section 3.4:

        alphaloop loop "run" "<goal>" [--seed N] [--budget USD] [--timeout S]
                              [--target-dsr F] [--model NAME]
                              [--data-dir DIR] [--dry-run] [--no-launch]

        alphaloop loop "replay" --run-id ID [--data-dir DIR]
        alphaloop loop "inspect" --run-id ID [--data-dir DIR]
        alphaloop loop "list" [--data-dir DIR]
        alphaloop loop "<goal>" [--no-launch]    (short form, defaults to run)
    """
    loop_p = subparsers.add_parser(
        "loop",
        help="v0.7 hybrid loop: end-to-end autonomous research",
    )
    loop_p.add_argument(
        "--no-launch",
        action="store_true",
        help="loop 完成后不自动启动 WebUI + 浏览器 (v0.7.2)",
    )
    loop_sub = loop_p.add_subparsers(dest="loop_command", help="loop 子命令")

    # --- run (default) ---
    run_p = loop_sub.add_parser("run", help="运行一次 hybrid loop")
    run_p.add_argument("goal", help="研究目标 (e.g. 'find alpha with DSR > 1.0')")
    run_p.add_argument("--run-id", help="显式 run_id (默认自动生成)")
    run_p.add_argument("--seed", type=int, help="随机种子")
    run_p.add_argument("--budget", type=float, default=5.0, help="成本上限 USD")
    run_p.add_argument("--timeout", type=int, default=6 * 3600, help="时间上限 秒")
    run_p.add_argument("--target-dsr", type=float, default=1.0, help="目标 DSR (gate A)")
    run_p.add_argument("--model", help="LLM 模型名 (默认从 $LLM_MODEL)")
    run_p.add_argument("--data-dir", default="./runs", help="runs/ 输出根目录")
    run_p.add_argument("--max-tasks", type=int, help="限制任务数 (默认走 planner)")
    run_p.add_argument(
        "--dry-run",
        action="store_true",
        help="只跑 N1+N2 (打印计划, 不执行 N3-N6)",
    )
    run_p.add_argument(
        "--git-repo-dir",
        default=".",
        help="git rev-parse HEAD 捕获目录 (N6)",
    )
    run_p.add_argument(
        "--no-launch",
        action="store_true",
        help="loop 完成后不自动启动 WebUI + 浏览器 (v0.7.2)",
    )
    run_p.set_defaults(loop_command="run")

    # --- replay ---
    replay_p = loop_sub.add_parser("replay", help="从持久化 artifacts 重放")
    replay_p.add_argument("--run-id", required=True, help="要重放的 run_id")
    replay_p.add_argument("--data-dir", default="./runs", help="runs/ 根目录")
    replay_p.set_defaults(loop_command="replay")

    # --- inspect ---
    inspect_p = loop_sub.add_parser("inspect", help="查看一次 run 的摘要")
    inspect_p.add_argument("--run-id", required=True, help="run_id")
    inspect_p.add_argument("--data-dir", default="./runs", help="runs/ 根目录")
    inspect_p.set_defaults(loop_command="inspect")

    # --- list ---
    list_p = loop_sub.add_parser("list", help="列出 --data-dir 下所有 run")
    list_p.add_argument("--data-dir", default="./runs", help="runs/ 根目录")
    list_p.set_defaults(loop_command="list")

    # 默认 goal 模式 (兼容 `alphaloop loop "<goal>"` 不带 sub)
    default_p = loop_sub.add_parser("__default__", help=argparse.SUPPRESS)
    default_p.add_argument("goal", help="研究目标")
    default_p.add_argument("--run-id", help="显式 run_id")
    default_p.add_argument("--seed", type=int, help="随机种子")
    default_p.add_argument("--budget", type=float, default=5.0)
    default_p.add_argument("--timeout", type=int, default=6 * 3600)
    default_p.add_argument("--target-dsr", type=float, default=1.0)
    default_p.add_argument("--model", help="LLM 模型名")
    default_p.add_argument("--data-dir", default="./runs")
    default_p.add_argument("--max-tasks", type=int)
    default_p.add_argument("--dry-run", action="store_true")
    default_p.add_argument("--git-repo-dir", default=".")
    default_p.add_argument(
        "--no-launch",
        action="store_true",
        help="loop 完成后不自动启动 WebUI + 浏览器 (v0.7.2)",
    )
    default_p.set_defaults(loop_command="run")

    loop_p.set_defaults(loop_command=None, func=None)


def _handle_loop(args: argparse.Namespace) -> int:
    """Dispatch the ``loop`` subcommand."""
    from alphaloop.runtime.worker import run_loop_command

    return run_loop_command(args)

def create_parser() -> argparse.ArgumentParser:
    """创建命令行解析器"""
    parser = argparse.ArgumentParser(
        prog="alphaloop",
        description="alphaloop — local-first overnight research lab",
    )

    # Patch parse_args to handle the short form:
    # `alphaloop loop <goal> [--no-launch] ...` → routes to `loop run`,
    # where <goal> is the first positional after `loop`. Without this,
    # argparse rejects the unknown positional with "invalid choice".
    orig_parse_args = parser.parse_args

    def _parse_args(args=None, namespace=None):  # type: ignore[override]
        import shlex

        # Tokenize if a string was passed.
        if isinstance(args, str):
            args = shlex.split(args)
        raw = list(args) if args is not None else sys.argv[1:]

        # Find the index of the `loop` subcommand.
        if "loop" in raw:
            i = raw.index("loop")
            after = raw[i + 1 :]
            # If the first token after `loop` is not a registered
            # subcommand and does not start with `-`, treat it as the
            # `goal` positional of the short form.
            known = {"run", "replay", "inspect", "list", "-h", "--help"}
            if after and not after[0].startswith("-") and after[0] not in known:
                # Insert a sentinel: route to the `run` subparser.
                new_raw = raw[: i + 1] + ["run"] + after
                return orig_parse_args(new_raw, namespace)

        return orig_parse_args(args, namespace)

    parser.parse_args = _parse_args  # type: ignore[assignment]

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
    fetch_parser.add_argument("--period", help="简写周期 (1d, 5d, 1mo, 3mo, 1y, 2y, 5y, 10y, ytd, max)")
    fetch_parser.add_argument("--start", help="开始日期 (YYYY-MM-DD)")
    fetch_parser.add_argument("--end", help="结束日期 (YYYY-MM-DD)")
    fetch_parser.add_argument(
        "--output", "-o", help="输出文件路径 (.csv 或 .json，按后缀决定)"
    )

    # report 命令 (v1.0 acceptance report)
    register_report(subparsers)

    register_export(subparsers)

    # Phase-2 runtime daemon and job commands
    register_jobs(subparsers)

    # loop 命令 (v0.7 hybrid loop)
    _register_loop(subparsers)

    # judge 命令 (v0.8 calibration: --calibration / --calibrate-prompt)
    register_judge_subcommand(subparsers)

    return parser


def main(args=None):
    """主入口函数"""
    parser = create_parser()
    parsed = parser.parse_args(args)

    if not parsed.command:
        parser.print_help()
        return 1

    try:
        if parsed.command == "backtest":
            return run_backtest(parsed)
        elif parsed.command == "optimize":
            return optimize_strategy(parsed)
        elif parsed.command == "fetch":
            return fetch_data(parsed)
        elif parsed.command == "report":
            return parsed.func(parsed)
        elif parsed.command == "export":
            return parsed.func(parsed)
        elif parsed.command in {"start", "submit", "status", "cancel", "resume"}:
            return parsed.func(parsed)
        elif parsed.command == "loop":
            return _handle_loop(parsed)
        elif parsed.command == "judge":
            return parsed.func(parsed)
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"错误: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
