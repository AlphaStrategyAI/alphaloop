from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alphaloop.contracts.bundle import ExportNotAllowed
from alphaloop.runtime.asb_export import export_found_asb
from alphaloop.runtime.store import JobStore

DEFAULT_DATA_DIR = "./runs"


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "export",
        help="export a FOUND candidate as an immutable .asb bundle",
    )
    parser.add_argument("candidate_id")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, type=Path)
    parser.add_argument("--output", "-o", required=True, type=Path)
    parser.set_defaults(func=run_export)


def run_export(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    store = JobStore(data_dir / ".alphaloop" / "state.db", data_dir)
    try:
        export_found_asb(
            store=store,
            data_dir=data_dir,
            run_id=args.run_id,
            candidate_id=args.candidate_id,
            output=args.output,
        )
    except KeyError:
        print(f"error: job not found: {args.run_id}", file=sys.stderr)
        return 2
    except (ExportNotAllowed, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(args.output)
    return 0
