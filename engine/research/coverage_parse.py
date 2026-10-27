from __future__ import annotations

import re

from engine.research.models import CoverageFloor


def parse_coverage_parts(message: str) -> tuple[int | None, int | None, float | None]:
    assets = re.search(r"至少\s*(\d+)\s*个", message)
    if assets is None:
        assets = re.search(
            r"\bat least\s+(\d+)\s+(?:names?|symbols?)\b",
            message,
            re.IGNORECASE,
        )
    years = re.search(r"(\d+)\s*年", message)
    if years is None and re.search(r"十\s*年|十年", message):
        years_val: int | None = 10
    elif years is not None:
        years_val = int(years.group(1))
    else:
        years_en = re.search(r"(\d+)\s*(?:years?|yrs?)\b", message, re.IGNORECASE)
        years_val = int(years_en.group(1)) if years_en else None
    missing = re.search(r"缺失不超过\s*(\d+(?:\.\d+)?)\s*%", message)
    if missing is None:
        missing = re.search(
            r"(?:no more than|at most)\s*(\d+(?:\.\d+)?)\s*%\s*missing\b",
            message,
            re.IGNORECASE,
        )
    if missing is None:
        missing = re.search(
            r"\bmissing(?:\s+rate)?\s+(?:no more than|at most)\s*(\d+(?:\.\d+)?)\s*%",
            message,
            re.IGNORECASE,
        )
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
    max_missing = missing if missing is not None else (current.max_missing_pct if current else None)
    if min_assets is None or min_years is None or max_missing is None:
        return None
    return CoverageFloor(min_assets=min_assets, min_years=min_years, max_missing_pct=max_missing)
