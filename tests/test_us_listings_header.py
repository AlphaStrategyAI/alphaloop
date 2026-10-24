"""The committed US listing file already names where it came from and when."""

from pathlib import Path

LISTING = Path(__file__).resolve().parents[1] / "engine" / "research" / "data" / "us_listings.txt"


def test_committed_listing_header_records_source_urls_and_fetch_date() -> None:
    header: list[str] = []
    for line in LISTING.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            break
        header.append(line)
    blob = "\n".join(header)
    assert "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt" in blob
    assert "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt" in blob
    assert "# generated: 2026-10-24" in blob
