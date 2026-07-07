"""
绩效指标计算
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class PerformanceMetrics:
    """绩效指标"""

    total_return: float = 0.0
    cagr: float = 0.0  # 年化收益率
    volatility: float = 0.0  # 年化波动率
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "total_return": self.total_return,
            "cagr": self.cagr,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": self.max_drawdown,
            "calmar_ratio": self.calmar_ratio,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
        }


def calculate_metrics(history: pd.DataFrame, risk_free_rate: float = 0.02) -> PerformanceMetrics:
    """
    计算回测绩效指标

    Args:
        history: 回测历史数据（需包含 total_value 列）
        risk_free_rate: 无风险利率（年化）

    Returns:
        绩效指标
    """
    if history.empty or "total_value" not in history.columns:
        return PerformanceMetrics()

    values = history["total_value"].values
    pd.to_datetime(history["date"])

    # 收益率
    total_return = (values[-1] / values[0]) - 1 if values[0] > 0 else 0.0

    # 计算日收益率
    returns = pd.Series(values).pct_change().dropna()

    # 交易天数
    trading_days = len(returns)
    years = trading_days / 252 if trading_days > 0 else 0

    # 年化收益率 (CAGR)
    if years > 0 and values[0] > 0:
        cagr = (values[-1] / values[0]) ** (1 / years) - 1
    else:
        cagr = 0.0

    # 年化波动率
    if len(returns) > 1:
        volatility = returns.std() * np.sqrt(252)
    else:
        volatility = 0.0

    # Sharpe Ratio
    if volatility > 0:
        sharpe_ratio = (cagr - risk_free_rate) / volatility
    else:
        sharpe_ratio = 0.0

    # Sortino Ratio（下行波动率）
    downside_returns = returns[returns < 0]
    if len(downside_returns) > 0:
        downside_std = downside_returns.std() * np.sqrt(252)
        sortino_ratio = (cagr - risk_free_rate) / downside_std if downside_std > 0 else 0.0
    else:
        sortino_ratio = 0.0

    # 最大回撤
    max_drawdown = calculate_max_drawdown(values)

    # Calmar Ratio
    if max_drawdown > 0:
        calmar_ratio = cagr / max_drawdown
    else:
        calmar_ratio = 0.0

    return PerformanceMetrics(
        total_return=total_return,
        cagr=cagr,
        volatility=volatility,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        max_drawdown=max_drawdown,
        calmar_ratio=calmar_ratio,
    )


def calculate_max_drawdown(values: np.ndarray) -> float:
    """
    计算最大回撤

    Args:
        values: 净值序列

    Returns:
        最大回撤（正值，如 0.2 表示 20%）
    """
    if len(values) < 2:
        return 0.0

    # 计算累计最大值
    peak = np.maximum.accumulate(values)

    # 计算回撤
    drawdown = (peak - values) / peak

    return np.max(drawdown) if len(drawdown) > 0 else 0.0


def calculate_rolling_metrics(
    returns: pd.Series,
    window: int = 252,
    risk_free_rate: float = 0.02,
) -> pd.DataFrame:
    """
    计算滚动指标

    Args:
        returns: 收益率序列
        window: 滚动窗口（交易日）
        risk_free_rate: 无风险利率

    Returns:
        滚动指标 DataFrame
    """
    rolling_vol = returns.rolling(window).std() * np.sqrt(252)
    rolling_return = returns.rolling(window).mean() * 252
    rolling_sharpe = (rolling_return - risk_free_rate) / rolling_vol.replace(0, np.nan)

    return pd.DataFrame(
        {
            "return": rolling_return,
            "volatility": rolling_vol,
            "sharpe": rolling_sharpe,
        }
    )
