"""Regenerate the US listing snapshot from the NASDAQ Trader symbol directory.

The directory changes daily, so CI checks the committed sha256 and does not
re-download. Refresh with network:

    python scripts/gen_us_listings.py
    python scripts/gen_us_listings.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
OUT = Path(__file__).resolve().parents[1] / "engine" / "research" / "data" / "us_listings.txt"
_CLASS = re.compile(r"^[A-Z]{1,6}(?:\.[A-Z])+$")


def _yahoo(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if _CLASS.fullmatch(symbol):
        return symbol.replace(".", "-")
    return symbol


def _rows(text: str, symbol_col: int, test_col: int) -> tuple[list[str], str]:
    lines = text.splitlines()
    created = ""
    symbols: list[str] = []
    for line in lines[1:]:
        if line.startswith("File Creation Time:"):
            created = line.split(":", 1)[1].strip().split("|", 1)[0].strip()
            continue
        parts = line.split("|")
        if len(parts) <= test_col or not parts[symbol_col].strip():
            continue
        if parts[test_col].strip().upper() == "Y":
            continue
        symbols.append(_yahoo(parts[symbol_col]))
    return symbols, created


def _download(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8")


def collect_symbols() -> tuple[list[str], str]:
    nasdaq, nasdaq_time = _rows(_download(NASDAQ_URL), 0, 3)
    other, other_time = _rows(_download(OTHER_URL), 0, 6)
    created = nasdaq_time or other_time
    return sorted(set(nasdaq + other)), created


def body_bytes(symbols: list[str]) -> bytes:
    return ("\n".join(symbols) + "\n").encode("utf-8")


def sha256_symbols(symbols: list[str]) -> str:
    return hashlib.sha256(body_bytes(symbols)).hexdigest()


def render(symbols: list[str], generated: str, directory_time: str) -> str:
    digest = sha256_symbols(symbols)
    header = "\n".join(
        [
            "# source: NASDAQ Trader symbol directory",
            f"# nasdaq: {NASDAQ_URL}",
            f"# other: {OTHER_URL}",
            "# excludes: test issues",
            "# class shares: dot form normalized to Yahoo hyphen (BRK.B -> BRK-B)",
            f"# generated: {generated}",
            f"# directory time: {directory_time}",
            f"# sha256: {digest}",
            "# terms: https://www.nasdaqtrader.com/Trader.aspx?id=symbollookup — see NOTICE",
            "",
        ]
    )
    return header + body_bytes(symbols).decode("utf-8")


def parse_committed(text: str) -> tuple[list[str], str | None]:
    symbols: list[str] = []
    digest: str | None = None
    for line in text.splitlines():
        if line.startswith("# sha256:"):
            digest = line.split(":", 1)[1].strip()
            continue
        if not line or line.startswith("#"):
            continue
        symbols.append(line.strip())
    return symbols, digest


def check() -> None:
    if not OUT.is_file():
        sys.exit(f"missing {OUT}")
    symbols, digest = parse_committed(OUT.read_text(encoding="utf-8"))
    expected = sha256_symbols(symbols)
    if digest != expected or symbols != sorted(set(symbols)):
        sys.exit(
            "us_listings.txt sha256 does not match its body. "
            "Regenerate with: python scripts/gen_us_listings.py"
        )
    print(f"{OUT} sha256 matches ({len(symbols)} symbols)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed sha256 does not match the symbol body",
    )
    args = parser.parse_args()
    if args.check:
        check()
        return
    symbols, created = collect_symbols()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(symbols, date.today().isoformat(), created), encoding="utf-8")
    print(f"wrote {OUT} ({len(symbols)} symbols, sha256 {sha256_symbols(symbols)})")


if __name__ == "__main__":
    main()
