"""
风险指标计算
"""

import numpy as np
import pandas as pd


def calculate_var(
    returns: pd.Series,
    confidence: float = 0.95,
    method: str = "historical",
) -> float:
    """
    计算 VaR (Value at Risk)

    Args:
        returns: 收益率序列
        confidence: 置信水平 (如 0.95 表示 95% VaR)
        method: 计算方法 ("historical", "parametric")

    Returns:
        VaR 值（负数表示损失）

    Examples:
        >>> returns = pd.Series([0.01, -0.02, 0.015, -0.01, 0.005])
        >>> var = calculate_var(returns, confidence=0.95)
        >>> print(f"95% VaR: {var:.2%}")
    """
    if returns.empty:
        return 0.0

    alpha = 1 - confidence

    if method == "historical":
        # 历史模拟法
        return np.percentile(returns, alpha * 100)

    elif method == "parametric":
        # 参数法（假设正态分布）
        mean = returns.mean()
        std = returns.std()
        z_score = np.percentile(np.random.standard_normal(10000), alpha * 100)
        return mean + z_score * std

    else:
        raise ValueError(f"Unknown method: {method}")


def calculate_cvar(
    returns: pd.Series,
    confidence: float = 0.95,
) -> float:
    """
    计算 CVaR/ES (Conditional Value at Risk / Expected Shortfall)

    CVaR 是超过 VaR 阈值的条件平均损失

    Args:
        returns: 收益率序列
        confidence: 置信水平

    Returns:
        CVaR 值
    """
    if returns.empty:
        return 0.0

    var = calculate_var(returns, confidence)
    # CVaR 是小于 VaR 的收益率的平均值
    return returns[returns <= var].mean() if len(returns[returns <= var]) > 0 else var


def calculate_beta(
    returns: pd.Series,
    market_returns: pd.Series,
) -> float:
    """
    计算 Beta 系数

    Beta = Cov(资产收益, 市场收益) / Var(市场收益)

    Args:
        returns: 资产收益率序列
        market_returns: 市场收益率序列

    Returns:
        Beta 值

    Examples:
        >>> beta = calculate_beta(stock_returns, spy_returns)
        >>> print(f"Beta: {beta:.2f}")
    """
    # 对齐数据
    aligned = pd.concat([returns, market_returns], axis=1).dropna()
    if len(aligned) < 2:
        return 1.0

    asset_rets = aligned.iloc[:, 0]
    market_rets = aligned.iloc[:, 1]

    covariance = asset_rets.cov(market_rets)
    market_variance = market_rets.var()

    if market_variance == 0:
        return 1.0

    return covariance / market_variance


def calculate_alpha(
    returns: pd.Series,
    market_returns: pd.Series,
    risk_free_rate: float = 0.02,
) -> float:
    """
    计算 Alpha (Jensen's Alpha)

    Alpha = 资产收益 - (无风险收益 + Beta * (市场收益 - 无风险收益))

    Args:
        returns: 资产收益率序列
        market_returns: 市场收益率序列
        risk_free_rate: 无风险利率（年化）

    Returns:
        Alpha 值
    """
    beta = calculate_beta(returns, market_returns)

    # 年化收益率
    asset_cagr = (1 + returns.mean()) ** 252 - 1
    market_cagr = (1 + market_returns.mean()) ** 252 - 1

    # CAPM 预期收益
    expected_return = risk_free_rate + beta * (market_cagr - risk_free_rate)

    return asset_cagr - expected_return


def calculate_tracking_error(
    returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """
    计算跟踪误差

    Args:
        returns: 组合收益率
        benchmark_returns: 基准收益率

    Returns:
        年化跟踪误差
    """
    diff = returns - benchmark_returns
    return diff.std() * np.sqrt(252)


def calculate_information_ratio(
    returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """
    计算信息比率

    IR = 超额收益 / 跟踪误差

    Args:
        returns: 组合收益率
        benchmark_returns: 基准收益率

    Returns:
        信息比率
    """
    excess_return = (returns.mean() - benchmark_returns.mean()) * 252
    tracking_error = calculate_tracking_error(returns, benchmark_returns)

    if tracking_error == 0:
        return 0.0

    return excess_return / tracking_error
