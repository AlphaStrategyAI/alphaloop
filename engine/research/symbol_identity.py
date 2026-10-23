"""Resolve a security identifier only when the text actually names one.

Six-digit numbers are codes only inside a real listing range, and never when they
are a quantity (a unit, a decimal, or a thousands separator). A bare US token is
a ticker only when a symbol directory, a ``$`` marker, or a non-word ticker shape
says so. Indicators and English words stay prose. Every accepted US ticker is
marked inferred so the confirm card can show it for editing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CN_CODE = re.compile(r"(?<!\d)(\d{6})(?:\.([A-Za-z]{2}))?(?!\d)")
_US_TICKER = re.compile(r"(?<![A-Za-z0-9$])([A-Z]{2,5}(?:\.[A-Z])?)(?![A-Za-z])")
_MARKED_TICKER = re.compile(r"(?<![A-Za-z0-9])\$([A-Za-z]{1,5}(?:\.[A-Za-z])?)(?![A-Za-z])")
_DECIMAL_TAIL = re.compile(r"[.．]\d")
_QUANTITY_UNIT = re.compile(
    r"\s*(?:万元|亿美元|万美元|美元|美金|港币|港元|人民币|块钱|元|块|万|亿|手|份|股(?!票)|[%％]"
    r"|USD\b|CNY\b|HKD\b|RMB\b|shares\b|share\b|dollars\b|dollar\b|yuan\b)",
    re.IGNORECASE,
)
_FIELD_SPLIT = re.compile(r"[、,，\s]+")
_ONE_FIELD_TOKEN = re.compile(r"(?:\d{6}(?:\.[A-Za-z]{2})?|[A-Za-z]{1,5}(?:\.[A-Za-z])?)")
_LISTED_SUFFIXES = frozenset({"SH", "SZ", "BJ"})

# First two digits → venue, when that prefix determines the exchange.
_SUFFIX_BY_PREFIX: dict[str, str] = {}
for _prefixes, _suffix in (
    (("60", "68", "51", "56", "58"), "SH"),
    (("00", "30", "15"), "SZ"),
    (("43", "83", "87", "92"), "BJ"),
):
    for _prefix in _prefixes:
        _SUFFIX_BY_PREFIX[_prefix] = _suffix

# Real listings we will not guess a venue for. Anything outside this set and the
# certain prefixes is not a code (100000, 610000, 400001).
_UNCERTAIN_PREFIX2 = frozenset({"11", "12", "13", "16", "18", "50", "52", "82", "88"})
_UNCERTAIN_PREFIX3 = frozenset({"900", "200"})

# Closed technical-analysis vocabulary. Not a list of English words.
_INDICATORS = frozenset({
    "RSI", "MACD", "KDJ", "BOLL", "ATR", "SMA", "EMA", "VWAP", "OBV", "CCI",
    "ADX", "STOCH", "ROC", "MFI", "DMI", "SAR", "PSY", "BIAS", "TRIX", "DMA", "EMV",
})

# Index products the dialogue already invites, even when they are not S&P members.
_OFFERED_US = frozenset({"SPY", "QQQ", "IWM", "DIA", "VOO", "VTI"})

# English words of 2–5 letters. A bare token here is prose unless `$` marks it
# or the symbol directory lists it (SPY is a word and a listed product).
_ENGLISH_WORDS = frozenset(
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
    find caps tech spy use look make need want word open close fast slow best next
    last same each both few once upon info note idea plan risk cash size time
    week name type kind form line list item part side area base case fact hand
    head home live move play read real seem show tell turn walk ways
    """.split()  # noqa: SIM905 — English lexicon, not a per-bug ticker blocklist
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


def listing_disposition(code: str) -> str | None:
    """``certain``, ``uncertain``, or None when the digits are not a listing."""
    if len(code) != 6 or not code.isdigit():
        return None
    if code[:2] in _SUFFIX_BY_PREFIX:
        return "certain"
    if code[:3] in _UNCERTAIN_PREFIX3 or code[:2] in _UNCERTAIN_PREFIX2:
        return "uncertain"
    return None


def is_cn_etf_symbol(symbol: str) -> bool:
    """China A-share ETF ranges the AkShare equity endpoint does not price."""
    if "." not in symbol:
        return False
    code, suffix = symbol.rsplit(".", 1)
    suffix = suffix.upper()
    if len(code) != 6 or not code.isdigit():
        return False
    if suffix == "SH" and code[:2] in {"51", "56", "58"}:
        return True
    return suffix == "SZ" and code[:2] == "15"


def extract_symbol_mentions(text: str, *, prose_filter: bool = True) -> tuple[SymbolMention, ...]:
    """Pull symbol-like tokens out of prose without inventing venues or tickers."""
    found: list[SymbolMention] = []
    occupied: list[tuple[int, int]] = []
    for match in _MARKED_TICKER.finditer(text):
        canonical = match.group(1).upper()
        found.append(SymbolMention(match.group(0), canonical, True))
        occupied.append(match.span())
    for match in _CN_CODE.finditer(text):
        if _overlaps(match.span(), occupied):
            continue
        if _is_quantity(text, match.end()):
            continue
        raw = match.group(0)
        code = match.group(1)
        suffix = match.group(2)
        if suffix is not None:
            suffix_up = suffix.upper()
            if suffix_up in _LISTED_SUFFIXES:
                found.append(SymbolMention(raw, f"{code}.{suffix_up}", False))
            else:
                found.append(SymbolMention(raw, None, False))
            occupied.append(match.span())
            continue
        kind = listing_disposition(code)
        if kind is None:
            continue
        if kind == "certain":
            inferred = suffix_for_listed_code(code)
            found.append(SymbolMention(raw, f"{code}.{inferred}", True))
        else:
            found.append(SymbolMention(raw, None, False))
        occupied.append(match.span())
    for match in _US_TICKER.finditer(text):
        if _overlaps(match.span(), occupied):
            continue
        token = match.group(1)
        if not _accept_bare_us(token, prose_filter=prose_filter):
            continue
        found.append(SymbolMention(token, token, True))
        occupied.append(match.span())
    return _dedupe(found)


def _is_quantity(text: str, end: int) -> bool:
    rest = text[end:]
    if _DECIMAL_TAIL.match(rest):
        return True
    return _QUANTITY_UNIT.match(rest) is not None


def _accept_bare_us(token: str, *, prose_filter: bool) -> bool:
    """Bare US tokens: ``$`` and non-words count; English words do not.

    The S&P directory is not enough on its own. LOW and TECH are both listings
    and ordinary words, so a directory hit must not rescue all-caps prose.
    Index products the dialogue already names (SPY, QQQ) are the exception.
    """
    if not prose_filter:
        return True
    base = token.split(".", 1)[0].upper()
    if base in _INDICATORS or token.upper() in _INDICATORS:
        return False
    if base in _OFFERED_US:
        return True
    return not (base.lower() in _ENGLISH_WORDS or token.lower() in _ENGLISH_WORDS)


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
