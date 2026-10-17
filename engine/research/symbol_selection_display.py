"""Single source for symbol-pool summary lines in desktop views."""

from __future__ import annotations

from typing import Any

def pool_version_number(version_id: str) -> str:
    if not version_id:
        return ""
    if version_id == "user":
        return "用户"
    if "_v" in version_id:
        suffix = version_id.rsplit("_v", 1)[-1]
        if suffix.isdigit():
            return suffix
    return version_id


def format_symbol_selection_summary(payload: dict[str, Any]) -> str:
    """``40 只 · 美股大市值 · 版本 1 · 2026-10-17 · 默认标的池``"""
    count = payload["count"]
    list_name = payload["listName"]
    version_id = str(payload.get("versionId") or payload.get("listVersion") or "")
    version_num = pool_version_number(version_id)
    parts = [f"{count} 只", list_name, f"版本 {version_num}"]
    generated = payload.get("generatedDate") or ""
    if generated:
        parts.append(str(generated))
    if payload.get("isDefaultPool") or payload.get("source") == "default_pool":
        parts.append("默认标的池")
    else:
        parts.append(str(payload.get("overrideNote") or "用户指定标的"))
    return " · ".join(parts)


def symbol_selection_summary_fields(
    *,
    count: int,
    list_name: str,
    version_id: str,
    generated_date: str,
    source: str,
    override_note: str | None,
    user_override: bool,
) -> dict[str, Any]:
    version_num = pool_version_number(version_id)
    base = {
        "count": count,
        "listName": list_name,
        "listVersion": version_num,
        "generatedDate": generated_date,
        "source": source,
        "overrideNote": override_note,
        "isDefaultPool": source == "default_pool",
    }
    base["summaryLine"] = format_symbol_selection_summary(
        {**base, "versionId": version_id}
    )
    return base
