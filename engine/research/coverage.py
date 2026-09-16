from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Literal

from engine.research.models import (
    ChangeClass,
    ConfirmKind,
    ConfirmRequest,
    CoverageFloor,
    CoverageShrink,
    CoverageSnapshot,
)


def within_floor(snapshot: CoverageSnapshot, floor: CoverageFloor) -> bool:
    return (
        len(snapshot.assets) >= floor.min_assets
        and snapshot.years >= float(floor.min_years)
        and snapshot.missing_pct <= floor.max_missing_pct
    )


def observed_floor(snapshot: CoverageSnapshot) -> CoverageFloor:
    return CoverageFloor(
        min_assets=len(snapshot.assets),
        min_years=floor(snapshot.years),
        max_missing_pct=snapshot.missing_pct,
    )


def _is_shrink(previous: CoverageSnapshot, observed: CoverageSnapshot) -> bool:
    return (
        len(observed.assets) < len(previous.assets)
        or observed.years < previous.years
        or observed.missing_pct > previous.missing_pct
    )


@dataclass(frozen=True, slots=True)
class CoverageDecision:
    action: Literal["continue", "record_shrink", "confirm"]
    shrink: CoverageShrink | None
    request: ConfirmRequest | None


def decide_coverage(
    previous: CoverageSnapshot | None,
    observed: CoverageSnapshot,
    floor: CoverageFloor,
    version_number: int,
    round_number: int,
) -> CoverageDecision:
    inside = within_floor(observed, floor)
    shrunk = previous is not None and _is_shrink(previous, observed)
    shrink = None
    if previous is not None and shrunk:
        shrink = CoverageShrink(
            shrink_id=f"c-v{version_number}-r{round_number}",
            version_number=version_number,
            round_number=round_number,
            before=previous,
            after=observed,
            reason=(
                f"覆盖从{len(previous.assets)}个资产/{previous.years:.1f}年/"
                f"缺失{previous.missing_pct:.1f}%缩到{len(observed.assets)}个资产/"
                f"{observed.years:.1f}年/缺失{observed.missing_pct:.1f}%"
            ),
            within_floor=inside,
        )
    if not inside:
        return CoverageDecision(
            "confirm",
            shrink,
            ConfirmRequest(
                request_id=f"coverage-v{version_number}-r{round_number}",
                kind=ConfirmKind.COVERAGE,
                proposed_change=shrink.reason if shrink else "数据覆盖将跌破最低容忍度",
                reason="继续研究需要低于用户认下的覆盖底线",
                effect="确认后开新版本并改写覆盖底线；拒绝则保持底线另找数据",
                change_class=ChangeClass.COVERAGE,
                patch=(("coverage_floor", observed_floor(observed)),),
            ),
        )
    if shrink is not None:
        return CoverageDecision("record_shrink", shrink, None)
    return CoverageDecision("continue", None, None)
