"""Human-readable export file names (new exports only; old paths remain valid)."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from engine.research.models import Research

_EXPORT_DISPLAY_TZ = ZoneInfo("Asia/Shanghai")


def _title_slug(research: Research, max_len: int = 28) -> str:
    raw = str(research.brief.thesis.value or "研究").strip()
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", raw).strip("-")
    if not slug:
        slug = "研究"
    return slug[:max_len]


def export_zip_filename(
    research: Research,
    kind: "research_record" | "strategy_pack",
    *,
    now: datetime | None = None,
) -> str:
    instant = now or datetime.now(_EXPORT_DISPLAY_TZ)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=_EXPORT_DISPLAY_TZ)
    else:
        instant = instant.astimezone(_EXPORT_DISPLAY_TZ)
    stamp = instant.strftime("%Y%m%d-%H%M%S")
    short_id = research.research_id.split("-")[0]
    label = "研究记录" if kind == "research_record" else "策略包"
    return f"{_title_slug(research)}-{short_id}-{label}-{stamp}.zip"
