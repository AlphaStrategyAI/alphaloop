"""Readable Chinese summaries for frozen method bodies (not raw JSON)."""

from __future__ import annotations

import json
from typing import Any

from engine.research.display_names import param_label

_FIELD_LABELS: dict[str, str] = {
    "revision": "修订标识",
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


def format_method_body_display(method_id: str, body: str) -> str:
    text = body.strip()
    if not text:
        return "（无正文）"
    try:
        parsed: Any = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text
    if not isinstance(parsed, dict):
        return text
    lines: list[str] = []
    if method_id.startswith("pit."):
        lines.append("时点一致性：仅使用决策当时可获得的信息。")
    for key, value in parsed.items():
        if key == "dimensions" and isinstance(value, list):
            lines.append(f"维度条目：{len(value)} 项")
            continue
        label = _FIELD_LABELS.get(key, param_label(key))
        if isinstance(value, float):
            text = f"{value:g}"
        else:
            text = str(value)
        lines.append(f"{label}：{text}")
    return "\n".join(lines) if lines else text
