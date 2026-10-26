"""Regenerate the common-English word list from wordfreq.

wordfreq is a dev-only tool. The engine and the sidecar read the generated
file and do not import wordfreq.

    pip install 'wordfreq==3.1.1'
    python scripts/gen_common_words.py
    python scripts/gen_common_words.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import sys
from datetime import date
from pathlib import Path

THRESHOLD = 4.5
WORDFREQ_VERSION = "3.1.1"
LANG = "en"
WORDLIST = "best"
OUT = Path(__file__).resolve().parents[1] / "engine" / "research" / "data" / "en_common_words.txt"


def collect_words() -> list[str]:
    try:
        from wordfreq import iter_wordlist, zipf_frequency
    except ImportError:
        sys.exit("wordfreq is required: pip install 'wordfreq==3.1.1'")
    try:
        found = importlib.metadata.version("wordfreq")
    except importlib.metadata.PackageNotFoundError:
        found = ""
    if found != WORDFREQ_VERSION:
        sys.exit(f"expected wordfreq {WORDFREQ_VERSION}, found {found or 'unknown'}")
    return sorted(
        word
        for word in iter_wordlist(LANG, WORDLIST)
        if word.isalpha() and zipf_frequency(word, LANG) >= THRESHOLD
    )


def body_bytes(words: list[str]) -> bytes:
    return ("\n".join(words) + "\n").encode("utf-8")


def sha256_words(words: list[str]) -> str:
    return hashlib.sha256(body_bytes(words)).hexdigest()


def render(words: list[str], generated: str) -> str:
    digest = sha256_words(words)
    header = "\n".join(
        [
            "# source: wordfreq 3.1.1 best English list",
            "# https://github.com/rspeer/wordfreq",
            "# threshold: Zipf >= 4.5",
            f"# generated: {generated}",
            f"# sha256: {digest}",
            "# license: CC-BY-SA 4.0 derivative of the wordfreq frequency data; see NOTICE",
            "",
        ]
    )
    return header + body_bytes(words).decode("utf-8")


def parse_committed(text: str) -> tuple[list[str], str | None]:
    words: list[str] = []
    digest: str | None = None
    for line in text.splitlines():
        if line.startswith("# sha256:"):
            digest = line.split(":", 1)[1].strip()
            continue
        if not line or line.startswith("#"):
            continue
        words.append(line)
    return words, digest


def check(words: list[str]) -> None:
    if not OUT.is_file():
        sys.exit(f"missing {OUT}")
    committed, digest = parse_committed(OUT.read_text(encoding="utf-8"))
    expected = sha256_words(words)
    if committed != words or digest != expected:
        sys.exit(
            "en_common_words.txt does not match wordfreq "
            f"{WORDFREQ_VERSION} Zipf >= {THRESHOLD}. "
            "Regenerate with: python scripts/gen_common_words.py"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed file differs from wordfreq",
    )
    args = parser.parse_args()
    words = collect_words()
    if args.check:
        check(words)
        print(f"{OUT} matches wordfreq {WORDFREQ_VERSION} ({len(words)} words)")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(words, date.today().isoformat()), encoding="utf-8")
    print(f"wrote {OUT} ({len(words)} words, sha256 {sha256_words(words)})")


if __name__ == "__main__":
    main()
