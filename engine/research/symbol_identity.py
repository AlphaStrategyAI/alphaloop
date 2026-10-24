"""Resolve a security identifier only when the text actually names one.

Six-digit numbers are codes only inside a real listing range. A real listing that
is skipped because it sits next to a quantity is still named, so the card can ask
instead of dropping it. A ``$`` marker is always a symbol. An all-caps real US
listing is a symbol, unless it is also a common English word, in which case the
card asks. A lowercase or mixed-case listing is a non-blocking hint. Indicators
and other English words stay prose.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_CN_CODE = re.compile(r"(?<!\d)(\d{6})(?:\.([A-Za-z]{2}))?(?!\d)")
# 1–5 letters so Ford's "F" is visible. A CJK neighbor is "A股", not a ticker.
# ASCII boundaries only. CJK is not an ASCII word character, so 美股AAPL均值回归
# still yields AAPL. The letter A in A股 is rejected later, not by this pattern.
_US_TOKEN = re.compile(
    r"(?<![A-Za-z0-9$])"
    r"([A-Za-z]{1,5}(?:[.\-][A-Za-z])?)"
    r"(?![A-Za-z0-9])"
)
_MARKED_TICKER = re.compile(
    r"(?<![A-Za-z0-9])\$([A-Za-z]{1,5}(?:[.\-][A-Za-z])?)(?![A-Za-z])"
)
_DECIMAL_TAIL = re.compile(r"[.．]\d")
# 股 is a share-count only when it is not the start of 股价, 股票, 股息, 股东, …
_QUANTITY_UNIT = re.compile(
    r"\s*(?:万元|亿美元|万美元|美元|美金|港币|港元|人民币|块钱|元|块|万|亿|手|份|"
    r"股(?![\u4e00-\u9fff])|[%％]|USD\b|CNY\b|HKD\b|RMB\b|shares\b|share\b|"
    r"dollars\b|dollar\b|yuan\b)",
    re.IGNORECASE,
)
_FIELD_SPLIT = re.compile(r"[、,，\s]+")
_ONE_FIELD_TOKEN = re.compile(
    r"(?:\d{6}(?:\.[A-Za-z]{2})?|[A-Za-z]{1,5}(?:[.\-][A-Za-z])?)"
)
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

# Closed technical-analysis and finance vocabulary. Not a list of English words.
# A member that is also a real listing is asked about; the others stay prose.
# Indicator words are always prose. A leading ``$`` is the only way one becomes a symbol.
_INDICATORS = frozenset({
    "RSI", "MACD", "KDJ", "BOLL", "ATR", "EMA", "SMA", "MA", "OBV", "CCI",
    "BIAS", "WR", "VWAP", "ADX", "STOCH", "ROC", "MFI", "DMI", "SAR", "PSY",
    "TRIX", "DMA", "EMV",
})
# Asked about only when the token is also a real US listing. Otherwise prose.
_LISTED_ASK_TERMS = frozenset({
    "GDP", "AI", "CEO", "USA", "CPI", "PMI", "IPO", "ETF", "ESG", "CFO", "NAV",
    "ROI", "AUM", "FED", "FOMC", "SEC", "NYSE", "YOY", "QOQ",
    "PE", "PB", "PS", "TTM", "EPS", "ROE", "ROA", "EBITDA", "ROIC",
})
_CN_MARKET = re.compile(r"A\s*股|沪|深|中国")
_US_MARKET = re.compile(r"美股|美国")
_SETTLEMENT = re.compile(r"\+\s*[0-2](?!\d)")

# Real listings that are not S&P 500 constituents. The dialogue already names these.
_INDEX_ETFS = frozenset({"SPY", "QQQ", "IWM", "DIA", "VOO", "VTI"})
_DATA_DIR = Path(__file__).resolve().parent / "data"
_COMMON_WORDS_PATH = _DATA_DIR / "en_common_words.txt"
_US_LISTINGS_PATH = _DATA_DIR / "us_listings.txt"
_A_SHARE = re.compile(r"\s*股")


@dataclass(frozen=True, slots=True)
class SymbolMention:
    raw: str
    canonical: str | None
    inferred: bool
    # symbol: use it. ask: real listing that is also a common word. hint: lowercase listing.
    kind: str = "symbol"


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


def _explicit_market(text: str) -> str | None:
    """``CN`` or ``US`` when the text names that market, else None when it names both or neither."""
    cn = _CN_MARKET.search(text) is not None
    us = _US_MARKET.search(text) is not None
    if cn and us:
        return None
    if cn:
        return "CN"
    if us:
        return "US"
    return None


def _caps_runs(text: str) -> list[list[re.Match[str]]]:
    """Runs of consecutive all-caps words, including words longer than a ticker."""
    token = re.compile(r"(?<![A-Za-z])[A-Z]+(?:[.\-][A-Z]+)?(?![A-Za-z])")
    runs: list[list[re.Match[str]]] = []
    current: list[re.Match[str]] = []
    for match in token.finditer(text):
        if not current:
            current = [match]
            continue
        between = text[current[-1].end():match.start()]
        if between and re.fullmatch(r"[\s,，、;；:.]+", between):
            current.append(match)
            continue
        if len(current) >= 3:
            runs.append(current)
        current = [match]
    if len(current) >= 3:
        runs.append(current)
    return runs


def _shout_spans(text: str) -> list[tuple[int, int]]:
    """All-caps runs that are prose, not a list of real non-word listings."""
    spans: list[tuple[int, int]] = []
    listings = us_listings()
    common = common_english_words()
    for run in _caps_runs(text):
        words = [match.group(0) for match in run]
        def _listed(word: str) -> bool:
            return _yahoo(word) in listings

        def _common(word: str) -> bool:
            return _word_key(word) in common

        # Every word is a real listing and none is a common word: 「SPY QQQ IWM」.
        if all(_listed(word) for word in words) and not any(_common(word) for word in words):
            continue
        # Any common word that is not itself a listing makes the whole run prose.
        if any(_common(word) and not _listed(word) for word in words):
            spans.append((run[0].start(), run[-1].end()))
    return spans


def extract_symbol_mentions(text: str, *, prose_filter: bool = True) -> tuple[SymbolMention, ...]:
    """Pull symbol-like tokens out of prose without inventing venues or tickers."""
    text = unicodedata.normalize("NFKC", text)
    found: list[SymbolMention] = []
    occupied: list[tuple[int, int]] = []
    for match in _MARKED_TICKER.finditer(text):
        found.append(SymbolMention(match.group(0), _yahoo(match.group(1)), True))
        occupied.append(match.span())
    for match in _CN_CODE.finditer(text):
        if _overlaps(match.span(), occupied):
            continue
        raw = match.group(0)
        code = match.group(1)
        suffix = match.group(2)
        if _is_quantity(text, match.end()):
            if suffix is not None and suffix.upper() in _LISTED_SUFFIXES:
                found.append(SymbolMention(raw, f"{code}.{suffix.upper()}", False, "amount"))
                occupied.append(match.span())
                continue
            venue = suffix_for_listed_code(code)
            if venue is not None:
                found.append(SymbolMention(code, f"{code}.{venue}", False, "amount"))
                occupied.append(match.span())
            elif listing_disposition(code) is not None:
                found.append(SymbolMention(code, None, False))
                occupied.append(match.span())
            continue
        if suffix is not None:
            suffix_up = suffix.upper()
            if suffix_up in _LISTED_SUFFIXES:
                found.append(_placed_cn(text, raw, f"{code}.{suffix_up}", False, prose_filter))
            else:
                found.append(SymbolMention(raw, None, False))
            occupied.append(match.span())
            continue
        kind = listing_disposition(code)
        if kind is None:
            continue
        if kind == "certain":
            inferred = suffix_for_listed_code(code)
            found.append(_placed_cn(text, raw, f"{code}.{inferred}", True, prose_filter))
        else:
            found.append(SymbolMention(raw, None, False))
        occupied.append(match.span())
    shouted = _shout_spans(text) if prose_filter else []
    for match in _US_TOKEN.finditer(text):
        if _overlaps(match.span(), occupied) or _overlaps(match.span(), shouted):
            continue
        mention = _us_mention(text, match, prose_filter=prose_filter)
        if mention is None:
            continue
        found.append(mention)
        occupied.append(match.span())
    # A lowercase listing is prose. The hint is only for a description that
    # would otherwise fall back to the default pool.
    if any(mention.kind in {"symbol", "ask", "finance", "amount", "mismatch"} for mention in found):
        found = [mention for mention in found if mention.kind != "hint"]
    return _dedupe(found)


def _placed_cn(
    text: str,
    raw: str,
    canonical: str,
    inferred: bool,
    prose_filter: bool,
) -> SymbolMention:
    if prose_filter and _explicit_market(text) == "US":
        return SymbolMention(raw, canonical, False, "mismatch")
    return SymbolMention(raw, canonical, inferred)


def _is_quantity(text: str, end: int) -> bool:
    rest = text[end:]
    if _DECIMAL_TAIL.match(rest):
        return True
    return _QUANTITY_UNIT.match(rest) is not None


def _yahoo(token: str) -> str:
    """Yahoo class-share form: ``BRK.B`` and ``BRK-B`` both store ``BRK-B``."""
    return token.upper().replace(".", "-")


def _word_key(token: str) -> str:
    return re.split(r"[.\-]", token, maxsplit=1)[0].lower()


def _all_caps(token: str) -> bool:
    letters = [char for char in token if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters)


def _is_indicator(token: str) -> bool:
    base = _word_key(token).upper()
    return base in _INDICATORS or token.upper() in _INDICATORS


@lru_cache(maxsize=1)
def common_english_words() -> frozenset[str]:
    """Zipf >= 4.5 alphabetic words. See the file header and NOTICE."""
    return _load_word_file(_COMMON_WORDS_PATH, lower=True)


def _load_word_file(path: Path, *, lower: bool = True) -> frozenset[str]:
    words: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        word = line.strip()
        if lower:
            word = word.lower()
        if word and not word.startswith("#"):
            words.add(word)
    return frozenset(words)


@lru_cache(maxsize=1)
def us_listings() -> frozenset[str]:
    """NASDAQ Trader directory in Yahoo form, plus the index ETFs already named."""
    symbols = set(_INDEX_ETFS)
    symbols.update(_load_word_file(_US_LISTINGS_PATH, lower=False))
    return frozenset(symbols)


def _is_cn_symbol(symbol: str) -> bool:
    return symbol.upper().endswith((".SH", ".SZ", ".BJ"))


def _term(token: str) -> str | None:
    base = _word_key(token).upper()
    if base in _LISTED_ASK_TERMS or token.upper() in _LISTED_ASK_TERMS:
        return "finance"
    return None


def _cn_single_letter(text: str, token: str) -> bool:
    if len(_word_key(token)) != 1 or _US_MARKET.search(text):
        return False
    return _CN_MARKET.search(text) is not None


def _us_mention(text: str, match: re.Match[str], *, prose_filter: bool) -> SymbolMention | None:
    token = match.group(1)
    if token.upper() in {"USD", "CNY", "HKD", "RMB"} and re.search(r"\d\s*$", text[: match.start()]):
        return None
    if token.upper() == "T" and _SETTLEMENT.match(text[match.end():]):
        return None
    if token.upper() == "A" and _A_SHARE.match(text[match.end():]):
        return None
    if _cn_single_letter(text, token):
        return None
    canonical = _yahoo(token)
    if not prose_filter:
        return SymbolMention(token, canonical, True)
    if _is_indicator(token):
        return None
    listed = canonical in us_listings()
    explicit = _explicit_market(text)
    key = _word_key(token)
    common = key in common_english_words()
    term = _term(token)
    if _all_caps(token):
        # A listed common word or finance term is asked about, even under an
        # explicit A-share sentence. It is never auto-recognized there.
        if listed and (common or term):
            kind = "ask" if common else "finance"
            return SymbolMention(token, canonical, False, kind)
        if listed and explicit == "CN" and not _is_cn_symbol(canonical):
            return SymbolMention(token, canonical, False, "mismatch")
        if listed:
            return SymbolMention(token, canonical, True)
        # GDP, CEO, and the other macro words are text unless they are listings.
        if term:
            return None
        letters = len(re.sub(r"[^A-Za-z]", "", token))
        if 2 <= letters <= 5 and not common:
            return SymbolMention(token, None, False, "unrecognized")
        return None
    if listed:
        return SymbolMention(token, canonical, False, "hint")
    return None


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
