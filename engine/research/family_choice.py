"""Confirm-card family answer: acknowledgement buttons and family chips.

The desktop renders the signed-off labels. This module only decides which
controls are open and which family ids belong on the chips.
"""

from __future__ import annotations

from engine.research.families import PRODUCT_FAMILY_IDS
from engine.research.family_intent import classify_thesis
from engine.research.models import Market, Research


def _thesis(research: Research) -> str:
    value = research.brief.thesis.value
    return value if isinstance(value, str) else ""


def show_ack(research: Research) -> bool:
    """The two mean-reversion answers. Hidden after 「不继续」 until a new family is chosen."""
    if research.mean_reversion_adopted or research.mean_reversion_declined:
        return False
    if research.repicked_family and research.repicked_family != "mean_reversion":
        return True
    return classify_thesis(_thesis(research)).outcome == "disclose"


def show_chips(research: Research) -> bool:
    """Family chips. A chosen family replaces the chips with the re-pick notice."""
    if research.repicked_family:
        return False
    if research.mean_reversion_declined or research.pending_non_mr_thesis:
        return True
    return classify_thesis(_thesis(research)).outcome == "block"


def reply_open(research: Research) -> bool:
    """Chat stays on so a typed answer and a button share one handler."""
    return show_ack(research) or show_chips(research)


def chip_ids(research: Research) -> list[str]:
    """Glossary order. A-share in this version can only run mean reversion."""
    universe = research.brief.universe.value
    if (
        universe is not None
        and not universe.market_unspecified
        and universe.market is Market.CN
    ):
        return ["mean_reversion"]
    return list(PRODUCT_FAMILY_IDS)


def family_choice_payload(research: Research) -> dict[str, object]:
    return {
        "meanReversionChoice": show_ack(research),
        "familyChipIds": chip_ids(research) if show_chips(research) else [],
    }
