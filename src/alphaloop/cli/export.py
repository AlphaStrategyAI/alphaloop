from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from alphaloop.contracts.bundle import ExportNotAllowed
from alphaloop.runtime.asb_export import export_found_asb
from alphaloop.runtime.morning import format_export_handoff
from alphaloop.runtime.store import JobStore

DEFAULT_DATA_DIR = "./runs"


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "export",
        help="export a FOUND candidate as an immutable .asb bundle",
    )
    parser.add_argument("candidate_id")
    parser.add_argument("--run-id")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, type=Path)
    parser.add_argument("--output", "-o", required=True, type=Path)
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the export receipt as JSON",
    )
    parser.set_defaults(func=run_export)


def run_export(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    store = JobStore(data_dir / ".alphaloop" / "state.db", data_dir)
    run_id = args.run_id
    if not run_id:
        jobs = store.list_jobs()
        if not jobs:
            print("error: no overnight job yet", file=sys.stderr)
            return 2
        run_id = jobs[0].run_id
    try:
        export_found_asb(
            store=store,
            data_dir=data_dir,
            run_id=run_id,
            candidate_id=args.candidate_id,
            output=args.output,
        )
    except KeyError:
        print(f"error: job not found: {run_id}", file=sys.stderr)
        return 2
    except (ExportNotAllowed, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    exported_path = str(args.output)
    if args.json:
        print(
            json.dumps(
                {
                    "candidate_id": args.candidate_id,
                    "exported_path": exported_path,
                    "research_outcome": "FOUND",
                },
                sort_keys=True,
            )
        )
        return 0
    print(
        format_export_handoff(
            candidate_id=args.candidate_id,
            exported_path=exported_path,
        ),
        end="",
    )
    return 0
