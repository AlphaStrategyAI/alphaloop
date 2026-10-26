#!/usr/bin/env python3
"""Bake the desktop version and git sha into the UI and the engine sidecar."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def app_version() -> str:
    return subprocess.check_output(
        [sys.executable, str(ROOT / "scripts" / "check_app_version.py"), "--print"],
        cwd=ROOT,
        text=True,
    ).strip()


def git_sha() -> str:
    override = os.environ.get("ALPHALOOP_GIT_SHA", "").strip()
    if override:
        return override
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip() or "unknown"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    version = app_version()
    sha = git_sha()
    payload = {"version": version, "gitSha": sha}
    info = ROOT / "engine" / "research" / "build_info.json"
    info.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    ts = ROOT / "apps" / "desktop" / "src" / "buildInfo.ts"
    ts.write_text(
        "/** Overwritten by scripts/write_build_info.py before a packaged build. */\n"
        f'export const appVersion = "{version}";\n'
        f'export const gitSha = "{sha}";\n',
        encoding="utf-8",
    )
    print(f"build info {version} {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
