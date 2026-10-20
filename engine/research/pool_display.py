"""Public names for the v2 default pools.

Records store the pool id only. These strings are display copy. English sits
beside the Chinese so a later catalog can take both without renaming the pool.
"""

from __future__ import annotations

_V2_COPY: dict[str, dict[str, str]] = {
    "us_equity_large_cap_v2": {
        "zh": "美股大市值池 · {count} 只 · 名单日 {date}",
        "en": "US large-cap universe · {count} names · list date {date}",
        "zh_note": "取自标普 500 在名单日的成分，非时点成分",
        "en_note": "Taken from S&P 500 membership on the list date; not point-in-time.",
    },
    "cn_equity_large_cap_v2": {
        "zh": "A 股大市值池 · {count} 只 · 名单日 {date}",
        "en": "China A-share large-cap universe · {count} names · list date {date}",
        "zh_note": "取自沪深 300 在名单日的成分，非时点成分",
        "en_note": "Taken from CSI 300 membership on the list date; not point-in-time.",
    },
}


def public_pool_copy(version_id: str, count: int, generated_date: str) -> dict[str, str] | None:
    template = _V2_COPY.get(version_id)
    if template is None:
        return None
    fields = {"count": count, "date": generated_date}
    return {
        "zh": template["zh"].format(**fields),
        "en": template["en"].format(**fields),
        "zh_note": template["zh_note"],
        "en_note": template["en_note"],
    }
