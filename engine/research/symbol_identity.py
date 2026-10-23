"""Resolve a security identifier only when the venue is explicit or the prefix is certain.

A description is prose. Uppercasing every word and treating it as a ticker is how
ordinary English becomes a symbol list. Exchange suffixes are added only for the
A-share and ETF prefixes whose venue is determined by the first two digits.
Anything else that looks like a code stays unresolved so the run can stop and ask.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CN_CODE = re.compile(r"(?<!\d)(\d{6})(?:\.([A-Za-z]{2}))?(?!\d)")
_US_TICKER = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2,5}(?:\.[A-Z])?)(?![A-Za-z])")
_FIELD_SPLIT = re.compile(r"[、,，\s]+")
_ONE_FIELD_TOKEN = re.compile(r"(?:\d{6}(?:\.[A-Za-z]{2})?|[A-Za-z]{1,5}(?:\.[A-Za-z])?)")
_LISTED_SUFFIXES = frozenset({"SH", "SZ", "BJ"})

# First two digits → venue. Prefixes not listed here are not guessed.
_SUFFIX_BY_PREFIX: dict[str, str] = {}
for _prefixes, _suffix in (
    (("60", "68", "51", "56", "58"), "SH"),
    (("00", "30", "15"), "SZ"),
    (("43", "83", "87", "92"), "BJ"),
):
    for _prefix in _prefixes:
        _SUFFIX_BY_PREFIX[_prefix] = _suffix

# Common English and market-prose words. A description written in capitals must
# not become a ticker list. Real tickers the user typed in capitals (SPY, BRK.B)
# are not in this set. The symbol field does not use it: that box is not prose.
_PROSE_WORDS = frozenset(
    """
    a an the and or of to in on for at by as is it be we he if do go no so up my
    me us am ok hi all any are was has had its our you can may out off per via
    not but from this that with into over only data cost year years more when
    will what about who than them some could time these then two first such like
    even most made after also many before must back where much your way well
    down each just those how too good very make world still own see men work long
    here both life being under never day same know while last might great old
    come since take three used right etf fund bond mean daily low high cap large
    stock price prices usd cny gdp cpi ipo otc nav aum ytd eps roe roi vol pit
    api lof reit qdii nyse szse hkex sse sh sz bj hk cn uk eu jp us
    """.split()  # noqa: SIM905 — a prose blocklist, not a data table
)


@dataclass(frozen=True, slots=True)
class SymbolMention:
    raw: str
    canonical: str | None
    inferred: bool


def suffix_for_listed_code(code: str) -> str | None:
    """Exchange suffix when the six-digit prefix determines the venue."""
    if len(code) != 6 or not code.isdigit():
        return None
    return _SUFFIX_BY_PREFIX.get(code[:2])


def extract_symbol_mentions(text: str, *, prose_filter: bool = True) -> tuple[SymbolMention, ...]:
    """Pull symbol-like tokens out of prose without inventing venues or tickers."""
    found: list[SymbolMention] = []
    occupied: list[tuple[int, int]] = []
    for match in _CN_CODE.finditer(text):
        raw = match.group(0)
        code = match.group(1)
        suffix = match.group(2)
        if suffix is not None:
            suffix_up = suffix.upper()
            if suffix_up in _LISTED_SUFFIXES:
                found.append(SymbolMention(raw, f"{code}.{suffix_up}", False))
            else:
                found.append(SymbolMention(raw, None, False))
        else:
            inferred = suffix_for_listed_code(code)
            if inferred is None:
                found.append(SymbolMention(raw, None, False))
            else:
                found.append(SymbolMention(raw, f"{code}.{inferred}", True))
        occupied.append(match.span())
    for match in _US_TICKER.finditer(text):
        if _overlaps(match.span(), occupied):
            continue
        token = match.group(1)
        base = token.split(".", 1)[0]
        if prose_filter and (base.lower() in _PROSE_WORDS or token.lower() in _PROSE_WORDS):
            continue
        found.append(SymbolMention(token, token, False))
        occupied.append(match.span())
    return _dedupe(found)


def parse_symbol_field(text: str) -> tuple[SymbolMention, ...]:
    """Parse the confirm-card symbol box. It is a symbol, not a sentence."""
    stripped = text.strip()
    if not stripped:
        return ()
    parts = [part for part in _FIELD_SPLIT.split(stripped) if part]
    if parts and all(_ONE_FIELD_TOKEN.fullmatch(part) for part in parts):
        found: list[SymbolMention] = []
        for part in parts:
            lifted = part.upper() if re.search(r"[A-Za-z]", part) else part
            found.extend(extract_symbol_mentions(lifted, prose_filter=False))
        if found:
            return _dedupe(found)
    mentions = extract_symbol_mentions(stripped)
    if mentions:
        return mentions
    return (SymbolMention(stripped, None, False),)


def _overlaps(span: tuple[int, int], occupied: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < other_end and end > other_start for other_start, other_end in occupied)


def _dedupe(mentions: list[SymbolMention]) -> tuple[SymbolMention, ...]:
    seen: set[str] = set()
    unique: list[SymbolMention] = []
    for mention in mentions:
        if mention.raw in seen:
            continue
        seen.add(mention.raw)
        unique.append(mention)
    return tuple(unique)
