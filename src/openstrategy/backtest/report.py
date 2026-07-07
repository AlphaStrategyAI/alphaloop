"""
回测报告生成
"""

import json
from pathlib import Path
from typing import Optional

import numpy as np

from ..backtest.engine import BacktestResult


class BacktestReport:
    """
    回测报告生成器

    生成文本、HTML、或 JSON 格式的回测报告

    Examples:
        >>> report = BacktestReport(result)
        >>> print(report.to_text())
        >>> report.to_html("report.html")
    """

    def __init__(self, result: BacktestResult):
        """
        初始化报告

        Args:
            result: 回测结果
        """
        self.result = result

    def to_text(self) -> str:
        """生成文本报告"""
        m = self.result.metrics

        lines = [
            "=" * 50,
            "Backtest Report",
            "=" * 50,
            "",
            "Performance Metrics:",
            f"  Total Return:     {m.total_return:>10.2%}",
            f"  CAGR:             {m.cagr:>10.2%}",
            f"  Volatility:       {m.volatility:>10.2%}",
            f"  Sharpe Ratio:     {m.sharpe_ratio:>10.2f}",
            f"  Sortino Ratio:    {m.sortino_ratio:>10.2f}",
            f"  Max Drawdown:     {m.max_drawdown:>10.2%}",
            f"  Calmar Ratio:     {m.calmar_ratio:>10.2f}",
            "",
            f"Number of Trades: {len(self.result.trades)}",
            f"Final Portfolio Value: ${self.result.portfolio.cash:,.2f}",
            "=" * 50,
        ]

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """生成字典格式报告"""
        return {
            "metrics": self.result.metrics.to_dict(),
            "config": {
                "initial_cash": self.result.config.initial_cash,
                "commission_rate": self.result.config.commission_rate,
            },
            "summary": self.result.summary(),
            "trades": self.result.trades.to_dict("records") if not self.result.trades.empty else [],
        }

    def to_json(self, filepath: Optional[str] = None) -> str:
        """
        生成 JSON 报告

        Args:
            filepath: 保存路径（可选）

        Returns:
            JSON 字符串
        """
        data = self.to_dict()
        json_str = json.dumps(data, indent=2, default=str)

        if filepath:
            Path(filepath).write_text(json_str)

        return json_str

    def to_html(self, filepath: Optional[str] = None) -> str:
        """
        生成 HTML 报告

        Args:
            filepath: 保存路径（可选）

        Returns:
            HTML 字符串
        """
        m = self.result.metrics

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Backtest Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 400px; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .positive {{ color: green; }}
                .negative {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>Backtest Report</h1>
            <h2>Performance Metrics</h2>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Total Return</td><td class="{'positive' if m.total_return > 0 else 'negative'}">{m.total_return:.2%}</td></tr>
                <tr><td>CAGR</td><td class="{'positive' if m.cagr > 0 else 'negative'}">{m.cagr:.2%}</td></tr>
                <tr><td>Volatility</td><td>{m.volatility:.2%}</td></tr>
                <tr><td>Sharpe Ratio</td><td>{m.sharpe_ratio:.2f}</td></tr>
                <tr><td>Sortino Ratio</td><td>{m.sortino_ratio:.2f}</td></tr>
                <tr><td>Max Drawdown</td><td class="negative">{m.max_drawdown:.2%}</td></tr>
                <tr><td>Calmar Ratio</td><td>{m.calmar_ratio:.2f}</td></tr>
            </table>
            <p>Number of Trades: {len(self.result.trades)}</p>
        </body>
        </html>
        """

        if filepath:
            Path(filepath).write_text(html)

        return html

    def plot_equity_curve(self, filepath: Optional[str] = None):
        """
        绘制权益曲线（需要 matplotlib）

        Args:
            filepath: 保存路径
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib not installed")
            return

        history = self.result.history

        fig, axes = plt.subplots(2, 1, figsize=(12, 8))

        # 权益曲线
        ax1 = axes[0]
        ax1.plot(history["date"], history["total_value"], label="Portfolio Value")
        ax1.set_title("Equity Curve")
        ax1.set_xlabel("Date")
        ax1.set_ylabel("Value")
        ax1.legend()
        ax1.grid(True)

        # 回撤
        ax2 = axes[1]
        values = history["total_value"].values
        peak = np.maximum.accumulate(values)
        drawdown = (peak - values) / peak
        ax2.fill_between(history["date"], drawdown, 0, color="red", alpha=0.3)
        ax2.set_title("Drawdown")
        ax2.set_xlabel("Date")
        ax2.set_ylabel("Drawdown")
        ax2.grid(True)

        plt.tight_layout()

        if filepath:
            plt.savefig(filepath)
        else:
            plt.show()
