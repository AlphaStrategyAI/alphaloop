"""Single source for symbol-pool summary lines in desktop views."""

from __future__ import annotations

from typing import Any

from engine.research.pool_display import public_pool_copy


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
    """v2 name omits the version. v1 stays ``40 只 · 美股大市值 · 版本 1 · …``."""
    if payload.get("listNote"):
        return str(payload["listName"])
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
    copy = public_pool_copy(version_id, count, generated_date)
    if copy is not None:
        list_name = copy["zh"]
    base = {
        "count": count,
        "listName": list_name,
        "listVersion": version_num,
        "generatedDate": generated_date,
        "source": source,
        "overrideNote": override_note,
        "isDefaultPool": source == "default_pool",
        "listNote": copy["zh_note"] if copy is not None else "",
        "listNameEn": copy["en"] if copy is not None else "",
        "listNoteEn": copy["en_note"] if copy is not None else "",
    }
    base["summaryLine"] = format_symbol_selection_summary(
        {**base, "versionId": version_id}
    )
    return base
