from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from engine.research.models import (
    AssetClass,
    Market,
    Research,
    ResearchStatus,
)


@dataclass(frozen=True, slots=True)
class ResearchListItem:
    research_id: str
    title: str
    universe_label: str
    status: ResearchStatus
    created_at: datetime
    updated_at: datetime


_MARKET = {Market.US: "美股", Market.CN: "A股"}
_ASSET = {AssetClass.EQUITY: "股票", AssetClass.BOND: "债券", AssetClass.FUND: "基金"}


def host_status(
    researches: tuple[Research, ...],
) -> Literal["awaiting_confirm", "running", "completed", "idle"]:
    if any(item.status is ResearchStatus.AWAITING_CONFIRM for item in researches):
        return "awaiting_confirm"
    if any(item.status is ResearchStatus.RUNNING for item in researches):
        return "running"
    if any(item.status is ResearchStatus.COMPLETED for item in researches):
        return "completed"
    return "idle"


def list_items(
    researches: tuple[Research, ...],
    status_filter: ResearchStatus | None,
) -> tuple[ResearchListItem, ...]:
    rows = []
    for item in researches:
        if status_filter is not None and item.status is not status_filter:
            continue
        universe = item.brief.universe.value
        rows.append(
            ResearchListItem(
                research_id=item.research_id,
                title=(item.brief.thesis.value or "未命名研究"),
                universe_label=(
                    f"{_MARKET[universe.market]} · {_ASSET[universe.asset_class]}"
                    if universe is not None
                    else "未锁定"
                ),
                status=item.status,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )
    return tuple(rows)


def thesis_divergence_hint(previous: str, proposed: str) -> str | None:
    old = set(previous)
    new = set(proposed)
    if not old or len(old & new) / len(old) >= 0.4:
        return None
    return "这也可以作为一条新研究重新开始。"
