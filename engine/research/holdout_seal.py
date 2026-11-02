"""Seal the dialogue holdout corpus.

The SHA covers the corpus file bytes exactly. Re-seal only after the
annotation owner locks a new label, and never to invent a model score.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def corpus_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m engine.research.holdout_seal <corpus.json>", file=sys.stderr)
        return 2
    print(corpus_sha256(Path(args[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
