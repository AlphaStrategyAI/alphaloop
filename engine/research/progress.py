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
from engine.research.state_machine import all_slots_locked


@dataclass(frozen=True, slots=True)
class ResearchListItem:
    research_id: str
    title: str
    universe_label: str
    status: ResearchStatus
    list_status: str
    created_at: datetime
    updated_at: datetime


def list_row_status(research: Research) -> str:
    """Desktop list pill: confirm-ready drafts use the same label as the confirm_run view."""
    if research.status is ResearchStatus.DRAFT and all_slots_locked(research.brief):
        return "confirm_run"
    if research.status is ResearchStatus.COMPLETED:
        from engine.export import strategy_pack_eligibility

        if not strategy_pack_eligibility(research).eligible:
            return ResearchStatus.ENDED.value
    return research.status.value


_MARKET = {Market.US: "美股", Market.CN: "A 股"}
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


def host_status_while_fetching(
    status: Literal["awaiting_confirm", "running", "completed", "idle"],
    *,
    fetching: bool,
) -> Literal["awaiting_confirm", "running", "completed", "idle"]:
    """A live quote load is running work, including while another study waits."""
    if fetching:
        return "running"
    return status


def list_items(
    researches: tuple[Research, ...],
    status_filter: ResearchStatus | None,
) -> tuple[ResearchListItem, ...]:
    rows = []
    for item in researches:
        if status_filter is not None and item.status is not status_filter:
            continue
        universe = item.brief.universe.value
        if universe is None or universe.market_unspecified:
            universe_label = "待选择"
        else:
            universe_label = f"{_MARKET[universe.market]} · {_ASSET[universe.asset_class]}"
        rows.append(
            ResearchListItem(
                research_id=item.research_id,
                # Empty means no stored thesis. The desktop renders the untitled label.
                # A saved title that is still the old Chinese label is mapped there too.
                title=(item.brief.thesis.value or ""),
                universe_label=universe_label,
                status=item.status,
                list_status=list_row_status(item),
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


def notification_event(
    before: ResearchStatus,
    after: ResearchStatus,
) -> Literal["awaiting_confirm", "completed", "ended"] | None:
    if after is ResearchStatus.AWAITING_CONFIRM and before is not ResearchStatus.AWAITING_CONFIRM:
        return "awaiting_confirm"
    if after is ResearchStatus.COMPLETED and before is not ResearchStatus.COMPLETED:
        return "completed"
    if after is ResearchStatus.ENDED and before is not ResearchStatus.ENDED:
        return "ended"
    return None

