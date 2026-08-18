from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from alphaloop.contracts.bundle import ExportNotAllowed, assert_exportable
from alphaloop.contracts.status import ResearchOutcome


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "export",
        help="export a FOUND candidate as an immutable .asb bundle",
    )
    parser.add_argument("candidate_id")
    parser.add_argument("--outcome", required=True, help="sealed research outcome")
    parser.add_argument(
        "--candidate-ids",
        required=True,
        help="comma-separated sealed candidate ids",
    )
    parser.add_argument("--output", "-o", required=True)
    parser.set_defaults(func=run_export)


def run_export(args: argparse.Namespace) -> int:
    try:
        outcome = ResearchOutcome(args.outcome)
    except ValueError:
        print(f"error: unknown outcome {args.outcome}", file=sys.stderr)
        return 2
    sealed_ids = tuple(item for item in args.candidate_ids.split(",") if item)
    try:
        assert_exportable(outcome, sealed_ids, args.candidate_id)
    except ExportNotAllowed as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    destination = Path(args.output)
    destination.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "candidate_id": args.candidate_id,
                "outcome": outcome.value,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    print(destination)
    return 0
