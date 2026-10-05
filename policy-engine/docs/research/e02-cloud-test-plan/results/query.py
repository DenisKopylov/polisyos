"""Find transferred E02 observations by unit, finding, cell, or test path.

Run from any directory. --details returns exact source blocks; dictionaries stay
as source locators to avoid repeating large outputs. Routes remain candidates.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    """Read a complete TSV index, honoring quoted cells."""
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def select(root: Path, args: argparse.Namespace) -> dict:
    """Join candidate routes with observed cells and exact source locations."""
    cells = rows(root / "cells.tsv")
    routes = rows(root / "routes.tsv")
    matching_routes = [
        r
        for r in routes
        if (not args.unit or r["unit"] == args.unit)
        and (not args.finding or r["finding_id"] == args.finding)
    ]
    canonical = json.loads((root.parent / "full-run/finding-routes.json").read_text())["findings"]
    ids = {r["cell_id"] for r in matching_routes if r["cell_id"]}
    selected = [
        r
        for r in cells
        if (not (args.unit or args.finding) or r["id"] in ids)
        and (not args.cell or r["id"] == args.cell)
        and (not args.path or args.path in r["path"])
        and (not args.failures_only or r["state"] != "PASS")
    ]
    selected_ids = {r["id"] for r in selected}
    displayed = selected[: args.limit]
    displayed_ids = {r["id"] for r in displayed}
    source_jobs = {r["job"] for r in displayed}
    events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
    selected_events = [e for e in events if displayed_ids & set(e["cell_ids"])]
    matching_block_count = len(selected_events)
    selected_events = selected_events[: args.block_limit]
    dictionaries = [e for e in events if not e["cell_ids"] and e["job"] in source_jobs]
    messages = []
    if args.details:
        source_lines = {
            job: (root / f"received/{job}.txt").read_text().splitlines() for job in source_jobs
        }
        for event in selected_events:
            event["source_text"] = "\n".join(
                source_lines[event["job"]][event["line_start"] - 1 : event["line_end"]]
            )
        requested_by_job = {
            job: set(
                re.findall(
                    r"\b[A-Z][A-Z0-9_]{1,40}\b",
                    "\n".join(e["source_text"] for e in selected_events if e["job"] == job),
                )
            )
            for job in source_jobs
        }

        def referenced_messages(value: object, requested: set[str]) -> list[tuple[str, object]]:
            found = []
            if isinstance(value, dict):
                identifier = next(
                    (
                        value[k]
                        for k in ["key", "error_id", "error"]
                        if isinstance(value.get(k), str) and value[k] in requested
                    ),
                    None,
                )
                if identifier:
                    found.append((identifier, value))
                else:
                    for key, item in value.items():
                        if key in requested:
                            found.append((key, item))
                        elif isinstance(item, (dict, list)):
                            found.extend(referenced_messages(item, requested))
            elif isinstance(value, list):
                for item in value:
                    found.extend(referenced_messages(item, requested))
            return found

        for block in dictionaries:
            text = "\n".join(
                source_lines[block["job"]][block["line_start"] - 1 : block["line_end"]]
            )
            value = json.loads(text)
            for key, reported in referenced_messages(value, requested_by_job[block["job"]]):
                messages.append(
                    {
                        "job": block["job"],
                        "message_key": key,
                        "source_file": block["source_file"],
                        "line_start": block["line_start"],
                        "line_end": block["line_end"],
                        "reported": reported,
                    }
                )
    return {
        "grade": "source_reported_compact_text_only; candidate_routes",
        "matching_cells": len(selected),
        "displayed_cells": len(displayed),
        "states": dict(sorted(Counter(r["state"] for r in selected).items())),
        "cells": displayed,
        "finding_routes": [
            r
            for r in matching_routes
            if r["cell_id"] in displayed_ids or (not r["cell_id"] and (args.unit or args.finding))
        ],
        "finding_basis": [
            r
            for r in canonical
            if r["finding_id"]
            in {
                route["finding_id"]
                for route in matching_routes
                if route["cell_id"] in displayed_ids
                or (not route["cell_id"] and (args.unit or args.finding))
            }
        ],
        "unrouted_findings": sorted({r["finding_id"] for r in matching_routes if not r["cell_id"]}),
        "matching_source_blocks": matching_block_count,
        "source_blocks": selected_events,
        "referenced_messages": messages,
        "available_job_context_blocks": len(dictionaries),
        "job_dictionary_or_context_blocks": dictionaries if args.job_context else [],
        "matching_route_cells": len(ids & selected_ids),
        "raw_archives_received": 0,
        "limitations": "Locators are structured source blocks, not a normalized event census. "
        "PASS does not establish semantic adequacy or finding closure.",
    }


def main() -> int:
    """Print bounded navigation output without running any pasted command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", choices=list("ABCDEF"))
    parser.add_argument("--finding")
    parser.add_argument("--cell")
    parser.add_argument("--path")
    parser.add_argument("--failures-only", action="store_true")
    parser.add_argument("--details", action="store_true")
    parser.add_argument("--job-context", action="store_true")
    parser.add_argument("--block-limit", type=int, default=40)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    if args.limit < 1 or args.block_limit < 1:
        parser.error("--limit and --block-limit must be positive")
    output = select(Path(__file__).resolve().parent, args)
    sys.stdout.write(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
