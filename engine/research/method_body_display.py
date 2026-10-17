"""Readable Chinese summaries for frozen method bodies (not raw JSON)."""

from __future__ import annotations

import json
import re
from typing import Any

from engine.research.display_names import format_display_number, param_label

_FIELD_LABELS: dict[str, str] = {
    "sharpe_oos_min_exclusive": "样本外夏普下限（不含等于）",
    "excess_ann_min_exclusive": "年化超额下限（不含等于）",
    "default_max_drawdown_floor": "最大回撤下限",
    "n_splits": "走样折数",
    "oos_to_is_min": "样本外/样本内比下限",
    "segments_min": "分段数下限",
    "same_sign_ratio_min": "同号比例下限",
    "top_bucket_pct": "头部桶占比（%）",
    "sharpe_impact_min": "夏普影响下限",
    "us_cost_bp": "美股成本（bp）",
    "cn_cost_bp": "A股成本（bp）",
    "net_excess_min_exclusive": "净超额下限（不含等于）",
    "category": "类别",
}

_METHOD_PURPOSE: dict[str, str] = {
    "scorecard.market": "用多维指标衡量策略是否达到最低可接受表现。",
    "overfit.walk": "走样分段检验，降低样本内偶然拟合的风险。",
    "stability.oos": "检验样本外分段方向是否稳定。",
    "crowding.load": "估计头部持仓拥挤对夏普的拖累。",
    "cost.turnover": "在换手成本下检验净超额是否仍为正。",
    "pit.consistency": "确保证据与回测只使用决策当时可获得的信息，杜绝前视偏差。",
}

_PIT_EN: dict[str, str] = {
    "Point-in-Time Consistency": "时点一致性",
    "Every evidence and backtest window uses only information available at decision time": (
        "证据与回测窗口仅使用决策当时可获得的信息。"
    ),
    "Lookahead bias detected: {violations}": "检测到前视偏差（详见违规项）",
    "pit_consistency": "时点一致性",
}

_REVISION_LABELS: dict[str, str] = {
    "scorecard-v1": "市场计分卡 · 内置第 1 版",
    "walk-v1": "走样检验 · 内置第 1 版",
    "stability-v1": "样本外稳定 · 内置第 1 版",
    "crowding-v1": "拥挤度 · 内置第 1 版",
    "cost-v1": "换手成本 · 内置第 1 版",
    "pit-v1": "时点一致性 · 内置第 1 版",
}


def method_purpose(method_id: str) -> str:
    return _METHOD_PURPOSE.get(method_id, "冻结验证方法定义。")


def revision_display_label(revision_token: str) -> str:
    if revision_token in _REVISION_LABELS:
        return _REVISION_LABELS[revision_token]
    if re.fullmatch(r"[a-z]+-v\d+", revision_token):
        return f"内置第 {revision_token.split('-v')[-1]} 版"
    return "内置修订"


def _format_bool(value: object) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    return str(value)


def _format_scalar(value: object) -> str:
    if isinstance(value, bool):
        return _format_bool(value)
    if isinstance(value, float):
        return format_display_number(value)
    if isinstance(value, int):
        return str(value)
    text = str(value)
    return _PIT_EN.get(text, text)


def _format_dimension(dim: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    name = _PIT_EN.get(str(dim.get("name", "")), str(dim.get("name", "维度")))
    lines.append(f"维度：{name}")
    desc = dim.get("description")
    if desc:
        lines.append(f"说明：{_format_scalar(desc)}")
    if "pass_threshold" in dim:
        raw = dim["pass_threshold"]
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            lines.append(f"通过阈值：{format_display_number(raw)}")
        else:
            lines.append(f"通过阈值：{_format_scalar(raw)}")
    comparison = dim.get("comparison")
    if comparison:
        cmp_map = {"eq": "等于", "gte": "不小于", "gt": "大于", "lte": "不大于", "lt": "小于"}
        lines.append(f"比较方式：{cmp_map.get(str(comparison), comparison)}")
    failure = dim.get("failure_display")
    if failure:
        lines.append(f"未通过提示：{_format_scalar(failure)}")
    unit = dim.get("unit")
    if unit and unit != "bool":
        lines.append(f"单位：{unit}")
    return lines


def format_method_body_display(method_id: str, body: str) -> str:
    text = body.strip()
    if not text:
        return "（无正文）"
    try:
        parsed: Any = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return _sanitize_free_text(text)
    if not isinstance(parsed, dict):
        return _sanitize_free_text(text)
    lines: list[str] = [f"用途：{method_purpose(method_id)}"]
    dimensions = parsed.get("dimensions")
    if isinstance(dimensions, list):
        for item in dimensions:
            if isinstance(item, dict):
                lines.extend(_format_dimension(item))
    for key, value in parsed.items():
        if key in {"revision", "dimensions"}:
            continue
        if key == "category" and method_id.startswith("pit."):
            lines.append(f"类别：{_format_scalar(value)}")
            continue
        label = _FIELD_LABELS.get(key, param_label(key))
        lines.append(f"{label}：{_format_scalar(value)}")
    return "\n".join(lines) if lines else "（无正文）"


def _sanitize_free_text(text: str) -> str:
    out = text
    for en, zh in _PIT_EN.items():
        out = out.replace(en, zh)
    out = re.sub(r"\\u[0-9a-fA-F]{4}", "", out)
    return out


def looks_like_json_body(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("{") and stripped.endswith("}")


def revision_token_from_body(body: str) -> str:
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return ""
    if isinstance(parsed, dict) and "revision" in parsed:
        return str(parsed["revision"])
    return ""
