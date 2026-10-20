"""Frontend I0-ci slice.

Hardcoded CJK in a file this diff touches fails the check.
The same text in a file the diff does not touch is only a warning, so other
in-flight branches are not turned red. Engine copy is out of scope (I2).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "desktop" / "src"
CJK = re.compile(r"[\u4e00-\u9fff]")
LEGACY_PREFIX = "«i18n-placeholder»"
PREFIX_ALLOWED = {
    "apps/desktop/src/i18n/placeholder.ts",
    "apps/desktop/src/i18n/placeholder.test.ts",
}
SKIP_PARTS = {"i18n"}


def changed_files(base: str | None) -> set[str] | None:
    if not base:
        return None
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None
    return {line.strip() for line in out.splitlines() if line.strip()}


def resolve_base() -> str | None:
    explicit = os.environ.get("I18N_SCAN_BASE")
    if explicit:
        return explicit
    ref = os.environ.get("GITHUB_BASE_REF")
    candidates = []
    if ref:
        candidates.append(f"origin/{ref}")
    candidates.extend(
        [
            "origin/cursor/i0-i18n-foundation-7598",
            "cursor/i0-i18n-foundation-7598",
        ]
    )
    for candidate in candidates:
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", candidate],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if probe.returncode == 0:
            return candidate
    return None


def violations(path: Path) -> list[str]:
    found: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if "i18n-allow" in line or not CJK.search(line):
            continue
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        found.append(f"{path.relative_to(ROOT)}:{number}: {stripped}")
    return found


def prefix_violations() -> list[str]:
    found: list[str] = []
    for path in SRC.rglob("*"):
        if path.suffix not in {".ts", ".tsx"} or ".test." in path.name:
            continue
        rel = str(path.relative_to(ROOT))
        if rel in PREFIX_ALLOWED:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if LEGACY_PREFIX in line:
                found.append(f"{rel}:{number}: leftover placeholder prefix in body text")
    return found


def main() -> int:
    prefixed = prefix_violations()
    if prefixed:
        print("i18n error: placeholder copy must use data-i18n-placeholder, not a body prefix")
        for line in prefixed:
            print(f"  fail {line}")
        return 1
    base = resolve_base()
    changed = changed_files(base)
    strict: list[str] = []
    warned: list[str] = []
    for path in SRC.rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        if ".test." in path.name or any(part in SKIP_PARTS for part in path.parts):
            continue
        found = violations(path)
        if not found:
            continue
        rel = str(path.relative_to(ROOT))
        if changed is None or rel in changed:
            strict.extend(found)
        else:
            warned.extend(found)
    if warned:
        print(f"i18n warning: {len(warned)} hardcoded CJK line(s) in files this diff does not touch")
        for line in warned:
            print(f"  warn {line}")
    if strict:
        print(f"i18n error: {len(strict)} hardcoded CJK line(s) in files this diff touches")
        for line in strict:
            print(f"  fail {line}")
        return 1
    scope = "all scanned frontend files" if changed is None else f"diff against {base}"
    print(f"i18n frontend scan passed ({scope})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
