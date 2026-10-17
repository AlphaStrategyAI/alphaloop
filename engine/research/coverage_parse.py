from __future__ import annotations

import re

from engine.research.models import CoverageFloor


def parse_coverage_parts(message: str) -> tuple[int | None, int | None, float | None]:
    assets = re.search(r"至少\s*(\d+)\s*个", message)
    years = re.search(r"(\d+)\s*年", message)
    if years is None and re.search(r"十\s*年|十年", message):
        years_val = 10
    elif years is not None:
        years_val = int(years.group(1))
    else:
        years_val = None
    missing = re.search(r"缺失不超过\s*(\d+(?:\.\d+)?)\s*%", message)
    return (
        int(assets.group(1)) if assets else None,
        years_val,
        float(missing.group(1)) if missing else None,
    )


def merge_coverage_floor(
    message: str,
    current: CoverageFloor | None,
) -> CoverageFloor | None:
    assets, years, missing = parse_coverage_parts(message)
    min_assets = assets if assets is not None else (current.min_assets if current else None)
    min_years = years if years is not None else (current.min_years if current else None)
    max_missing = (
        missing
        if missing is not None
        else (current.max_missing_pct if current else None)
    )
    if min_assets is None or min_years is None or max_missing is None:
        return None
    return CoverageFloor(min_assets=min_assets, min_years=min_years, max_missing_pct=max_missing)
