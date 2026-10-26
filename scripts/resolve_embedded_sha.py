#!/usr/bin/env python3
"""Print the git commit a packaged build should embed.

Tag builds use ``git rev-parse HEAD^{commit}`` after checkout of the tag.
That is the tagged commit. An annotated tag's ``github.sha`` can be the tag
object; when that object is in the checkout it is peeled and must match HEAD.
Pull-request and other builds keep ``GITHUB_SHA`` (for a pull request, GitHub's
merge commit).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def choose_embedded_sha(
    *,
    ref: str,
    github_sha: str,
    head_commit: str,
    peeled_github_sha: str | None,
) -> str:
    if ref.startswith("refs/tags/"):
        if peeled_github_sha and peeled_github_sha != head_commit:
            raise SystemExit(
                "tagged commit mismatch: "
                f"github.sha peels to {peeled_github_sha} but checkout HEAD is {head_commit}"
            )
        return head_commit
    if github_sha:
        return github_sha
    return head_commit


def _rev_parse(spec: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", spec],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def resolve_embedded_sha() -> str:
    ref = os.environ.get("GITHUB_REF", "")
    github_sha = os.environ.get("GITHUB_SHA", "").strip()
    head = _rev_parse("HEAD^{commit}") or _rev_parse("HEAD") or ""
    peeled = _rev_parse(f"{github_sha}^{{commit}}") if github_sha else None
    sha = choose_embedded_sha(
        ref=ref,
        github_sha=github_sha,
        head_commit=head,
        peeled_github_sha=peeled,
    )
    if ref.startswith("refs/tags/"):
        print(
            f"tag {os.environ.get('GITHUB_REF_NAME', ref)} embeds {sha} "
            f"via git rev-parse HEAD^{{commit}} (github.sha={github_sha or 'unset'})",
            file=sys.stderr,
        )
    elif github_sha:
        print(f"ref {ref or '(local)'} embeds GITHUB_SHA {sha}", file=sys.stderr)
    else:
        print(f"local build embeds git rev-parse HEAD {sha}", file=sys.stderr)
    return sha


def main() -> int:
    sha = resolve_embedded_sha()
    if not sha:
        print("could not resolve an embedded commit", file=sys.stderr)
        return 1
    print(sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
