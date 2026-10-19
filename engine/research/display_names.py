"""Central Chinese labels for user-facing copy (ids stay in advanced/export only)."""

from __future__ import annotations

import math
import re
from fractions import Fraction

METHOD_IDS: dict[str, str] = {
    "scorecard.market": "市场计分卡",
    "pit.consistency": "时点一致性",
    "overfit.walk": "分段稳健性检验",
    "stability.oos": "样本外稳定",
    "crowding.load": "集中度",
    "cost.turnover": "换手成本",
}

GATE_IDS: dict[str, str] = {
    "completed": "研究状态未完成",
    "all_current_methods_passed": "冻结验证方法未全部通过",
    "no_pending_confirm": "仍有待确认项",
    "all_reverifies_passed": "重新验证未全部通过",
    "pit_executed_and_passed": "时点一致性未通过或未执行",
}

MODEL_FAMILY: dict[str, str] = {
    "mean_reversion": "均值回归",
}

PARAM_NAMES: dict[str, str] = {
    "lookback_days": "回看天数",
    "entry_z": "入场 Z 值",
    "signal_definition": "信号定义",
    "feature_set": "特征集",
    "model_family": "模型族",
}

DATA_SOURCE: dict[str, str] = {
    "yahoo_daily": "雅虎日线",
    "akshare_sina_daily": "AkShare 日线（新浪优先）",
}

POOL_VERSION: dict[str, str] = {
    "us_equity_large_cap_v1": "美股大市值（版本 1）",
    "cn_equity_large_cap_v1": "A股大市值（版本 1）",
}

INTERNAL_ID_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?:scorecard\.market|pit\.consistency|overfit\.walk|stability\.oos|"
    r"crowding\.load|cost\.turnover|us_equity_large_cap_v1|cn_equity_large_cap_v1|yahoo_daily|akshare_sina_daily|"
    r"mean_reversion|lookback_days)"
)


def method_label(method_id: str) -> str:
    return METHOD_IDS.get(method_id, method_id)


def gate_check_label(check_id: str) -> str:
    return GATE_IDS.get(check_id, check_id)


def gate_blocker_message(check_id: str) -> str:
    return f"{gate_check_label(check_id)}，暂不能导出策略包"


def export_blocker_messages(failed_checks: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(gate_blocker_message(item) for item in failed_checks)


def param_label(name: str) -> str:
    return PARAM_NAMES.get(name, name)


def format_param_change(param: str, before: str, after: str) -> str:
    return f"{param_label(param)}：{before} → {after}"


def format_model_token(token: str) -> str:
    text = token
    for key, label in MODEL_FAMILY.items():
        text = text.replace(key, label)
    for key, label in PARAM_NAMES.items():
        text = text.replace(key, label)
    return text


def pool_version_label(version_id: str) -> str:
    return POOL_VERSION.get(version_id, version_id)


def format_display_number(value: float | int) -> str:
    """User-facing threshold/scalar (fractions preferred, else compact percent/decimal)."""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, float):
        return str(value)
    for max_den in (3, 4, 6, 8, 12):
        frac = Fraction(value).limit_denominator(max_den)
        if frac.denominator != 1 and math.isclose(float(frac), value, rel_tol=0, abs_tol=1e-9):
            return f"{frac.numerator}/{frac.denominator}"
    if math.isclose(value, round(value)):
        return str(int(round(value)))
    if 0 < abs(value) < 1:
        return f"{value * 100:.1f}%"
    return f"{value:.4g}"


def data_source_label(source_id: str) -> str:
    return DATA_SOURCE.get(source_id, source_id)


def localize_user_string(text: str) -> str:
    if not text:
        return text
    out = text
    for method_id, label in METHOD_IDS.items():
        out = out.replace(method_id, label)
    for key, label in MODEL_FAMILY.items():
        out = out.replace(key, label)
    for key, label in PARAM_NAMES.items():
        out = out.replace(key, label)
    for key, label in POOL_VERSION.items():
        out = out.replace(key, label)
    for key, label in DATA_SOURCE.items():
        out = out.replace(key, label)
    return out


def contains_internal_leak(text: str) -> bool:
    if INTERNAL_ID_PATTERN.search(text):
        return True
    if re.search(r"\blookback_days\b", text):
        return True
    if re.search(r"[a-z]+_[a-z]+", text) and "example" not in text.lower():
        if re.search(r"(scorecard|pit\.|overfit|stability|crowding|cost\.)", text):
            return True
    return False
