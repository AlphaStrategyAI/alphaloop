"""Which price source a new research may show as already selected.

Product owner decision for #151 (based on 42cefd4):

Auto-preselect a price source only when, for that market, there is exactly
one price source that is NOT unlicensed AND is already configured/available
(for example a user-imported local file). In every other case — zero such
sources, or two or more — the choice is Not selected / 待选择.

Yahoo and AkShare are unlicensed. They are never preselected, even after the
user has ticked the personal-research acknowledgement. That acknowledgement
stays once per source; ticking it once is still enough to run. It never
causes preselection, and the app does not remember the last chosen source
for a new research.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.research.display_names import data_source_label
from engine.research.models import Market
from engine.research.source_acknowledgement import acknowledged_at, is_unlicensed_source

_CONFIGURED_KEY = "configuredPriceSources"


@dataclass(frozen=True, slots=True)
class PriceSource:
    """One price source the confirm card can offer for a market."""

    source_id: str
    label: str
    unlicensed: bool
    configured: bool
    market: Market


def preselect_price_source(sources: tuple[PriceSource, ...] | list[PriceSource]) -> str | None:
    """Return the one source id to preselect, or None when the card stays blank.

    See the module docstring for the #151 rule. Unlicensed sources never
    qualify, whether or not their acknowledgement has been ticked. A licensed
    source qualifies only when it is already configured. Exactly one qualifier
    is preselected. Zero or two-or-more qualifiers leave the choice empty.
    """
    eligible: list[str] = []
    for source in sources:
        if source.unlicensed or not source.configured:
            continue
        if source.source_id not in eligible:
            eligible.append(source.source_id)
    if len(eligible) == 1:
        return eligible[0]
    return None


def _read_settings(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return loaded


def _write_settings(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def save_configured_licensed_source(
    path: Path,
    *,
    source_id: str,
    label: str,
    market: Market,
) -> None:
    """Record one user-owned price source, such as an imported local file.

    Unlicensed ids are refused. This list is not a memory of the last pick.
    """
    if is_unlicensed_source(source_id):
        raise ValueError(f"unlicensed sources are not configured defaults: {source_id}")
    payload = _read_settings(path)
    current = payload.get(_CONFIGURED_KEY)
    rows = [item for item in current if isinstance(item, dict)] if isinstance(current, list) else []
    rows = [item for item in rows if item.get("id") != source_id]
    rows.append({"id": source_id, "label": label, "market": market.value})
    payload[_CONFIGURED_KEY] = rows
    _write_settings(path, payload)


def configured_licensed_sources(path: Path, market: Market) -> tuple[PriceSource, ...]:
    """Licensed sources the user has already configured for this market."""
    raw = _read_settings(path).get(_CONFIGURED_KEY)
    if not isinstance(raw, list):
        return ()
    found: list[PriceSource] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        source_id = item.get("id")
        label = item.get("label")
        item_market = item.get("market")
        if not isinstance(source_id, str) or not source_id:
            continue
        if not isinstance(label, str) or not label:
            continue
        if item_market != market.value:
            continue
        if is_unlicensed_source(source_id):
            continue
        found.append(
            PriceSource(
                source_id=source_id,
                label=label,
                unlicensed=False,
                configured=True,
                market=market,
            )
        )
    found.sort(key=lambda source: source.source_id)
    return tuple(found)


def builtin_unlicensed_source(market: Market) -> PriceSource | None:
    """The built-in unlicensed price source for a market, if this app has one."""
    if market is Market.US:
        source_id = "yahoo_daily"
    elif market is Market.CN:
        source_id = "akshare_sina_daily"
    else:
        return None
    return PriceSource(
        source_id=source_id,
        label=data_source_label(source_id),
        unlicensed=True,
        configured=True,
        market=market,
    )


def available_price_sources(market: Market, settings_path: Path) -> tuple[PriceSource, ...]:
    """Licensed configured sources for the market, then its unlicensed built-in."""
    sources = list(configured_licensed_sources(settings_path, market))
    builtin = builtin_unlicensed_source(market)
    if builtin is not None:
        sources.append(builtin)
    return tuple(sources)


def apply_price_source_choice(
    selection: dict[str, Any],
    *,
    market: Market | None,
    explicit_source_id: str,
    settings_path: Path,
) -> None:
    """Fill the confirm-card source fields from ``preselect_price_source``.

    ``explicit_source_id`` is a choice already stored on this research. A new
    research has none. The last research's source is not consulted.
    """
    if market is None:
        sources: tuple[PriceSource, ...] = ()
    else:
        sources = available_price_sources(market, settings_path)
    explicit = explicit_source_id.strip()
    preselected = None if explicit else preselect_price_source(sources)
    selected = explicit or preselected or ""
    by_id = {source.source_id: source for source in sources}
    if selected and selected not in by_id:
        label = data_source_label(selected)
        by_id[selected] = PriceSource(
            source_id=selected,
            label=label,
            unlicensed=is_unlicensed_source(selected),
            configured=True,
            market=market or Market.US,
        )
        sources = tuple(by_id[source.source_id] for source in (*sources, by_id[selected]))
    selection["priceSources"] = [
        {
            "id": source.source_id,
            "label": source.label,
            "unlicensed": source.unlicensed,
            "acknowledgedAt": (
                acknowledged_at(source.source_id, settings_path) if source.unlicensed else None
            ),
        }
        for source in sources
    ]
    selection["dataSourcePending"] = not bool(selected)
    selection["dataSourceId"] = selected or None
    if selected and selected in by_id:
        selection["dataSource"] = by_id[selected].label
    else:
        selection["dataSource"] = "待选择"
    chosen = by_id.get(selected)
    acked = None
    if chosen is not None and chosen.unlicensed:
        acked = acknowledged_at(chosen.source_id, settings_path)
    elif not selected:
        builtin = builtin_unlicensed_source(market) if market is not None else None
        if builtin is not None:
            acked = acknowledged_at(builtin.source_id, settings_path)
    selection["unlicensedAcknowledgedAt"] = acked
    selection["unlicensedAcknowledgementRequired"] = bool(
        chosen is not None and chosen.unlicensed and not acked
    )
