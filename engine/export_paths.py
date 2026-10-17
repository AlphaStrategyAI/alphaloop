"""Human-readable export file names (new exports only; old paths remain valid)."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from engine.research.models import Research


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
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    short_id = research.research_id.split("-")[0]
    label = "研究记录" if kind == "research_record" else "策略包"
    return f"{_title_slug(research)}-{short_id}-{label}-{stamp}.zip"
