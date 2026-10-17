#!/usr/bin/env python3
"""Manual P0 smoke: export research_record + view helpers (no GUI)."""

from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    from engine.export import build_research_record_pack, strategy_pack_eligibility
    from engine.research.desktop_view import rounds_for_desktop, universe_label_for
    from tests.test_export_pack import completed_research

    research = completed_research()
    eligibility = strategy_pack_eligibility(research)
    out = REPO_ROOT / "artifacts" / "e2e-smoke"
    out.mkdir(parents=True, exist_ok=True)
    pack = build_research_record_pack(research, out / "record.zip")
    with zipfile.ZipFile(pack) as archive:
        why = json.loads(archive.read("why_not_live.json"))
    rounds = rounds_for_desktop(research, research.current_version_number or 1)
    print(
        json.dumps(
            {
                "universe_label": universe_label_for(research),
                "round_logic_sample": rounds[0]["logicStatement"]["statement"][:80]
                if rounds
                else None,
                "failed_checks": list(eligibility.failed_checks),
                "why_not_live": why.get("failed_checks"),
                "record_zip": str(pack),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
