"""Tag builds embed the tagged commit, not an annotated tag object."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "resolve_embedded_sha",
    ROOT / "scripts" / "resolve_embedded_sha.py",
)
assert SPEC and SPEC.loader
resolve = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resolve)
choose_embedded_sha = resolve.choose_embedded_sha


def test_tag_build_uses_the_checked_out_commit() -> None:
    sha = choose_embedded_sha(
        ref="refs/tags/v0.9.0",
        github_sha="tag-object",
        head_commit="abc123",
        peeled_github_sha="abc123",
    )
    assert sha == "abc123"


def test_tag_build_accepts_a_lightweight_tag_sha_that_cannot_be_peeled() -> None:
    sha = choose_embedded_sha(
        ref="refs/tags/v0.9.0",
        github_sha="abc123",
        head_commit="abc123",
        peeled_github_sha=None,
    )
    assert sha == "abc123"


def test_tag_build_rejects_a_peeled_sha_that_is_not_head() -> None:
    with pytest.raises(SystemExit, match="tagged commit mismatch"):
        choose_embedded_sha(
            ref="refs/tags/v0.9.0",
            github_sha="tag-object",
            head_commit="abc123",
            peeled_github_sha="def456",
        )


def test_pull_request_build_keeps_github_sha() -> None:
    sha = choose_embedded_sha(
        ref="refs/pull/149/merge",
        github_sha="ecdff18",
        head_commit="branch-head",
        peeled_github_sha="ecdff18",
    )
    assert sha == "ecdff18"
