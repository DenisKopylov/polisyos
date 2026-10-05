"""Rebuild navigation indexes from the complete transferred E02 text set.

This verifies transfer and index integrity, never product behavior or VM receipts.
Run with --check to reject any derived-file drift; --write rebuilds the indexes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

CELL = re.compile(r"F\d{2}-(?:P\d{3}|R\d+-(?:normal|removal|restored))")
FIELDS = [
    "id",
    "job",
    "source_sha",
    "path",
    "state",
    "collected",
    "calls",
    "call_pass",
    "call_failed",
    "setup_error",
    "teardown_error",
    "skip",
    "xfail",
    "xpass",
    "collection_skip",
    "collection_error",
    "wall_s",
    "rss_kib",
    "receipt_status",
    "source_file",
    "source_line",
    "extra_json",
]


def require(condition: bool, message: str) -> None:
    """Reject a broken source binding or incomplete index."""
    if not condition:
        raise ValueError(message)


def compact(value: object) -> str:
    """Return deterministic JSON without unnecessary whitespace."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def cell_references(value: object) -> set[str]:
    """Find standalone structured cell values, ignoring IDs inside error prose."""
    if isinstance(value, str):
        return {value} if CELL.fullmatch(value) else set()
    if isinstance(value, dict):
        return set().union(*(cell_references(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(cell_references(item) for item in value))
    return set()


def tsv(rows: list[dict], fields: list[str]) -> str:
    """Serialize rows with proper quoting, including embedded newlines."""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fields, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def json_blocks(text: str) -> list[tuple[int, int, object, bool]]:
    """Read line-start JSON and F15 @JSON groups without executing source text."""
    decoder = json.JSONDecoder()
    blocks = []
    offset = 0
    consumed = 0
    lines = text.splitlines(keepends=True)
    for number, line in enumerate(lines, 1):
        start = offset + len(line) - len(line.lstrip())
        stripped = line.lstrip()
        grouped = stripped.startswith("@{")
        if start >= consumed and (stripped.startswith(("{", "[")) or grouped):
            decode_start = start + int(grouped)
            try:
                value, length = decoder.raw_decode(text[decode_start:])
            except json.JSONDecodeError:
                pass
            else:
                end = decode_start + length
                last = text.count("\n", 0, end) + 1
                if grouped:
                    while last < len(lines) and re.match(r"M\d+\t", lines[last]):
                        last += 1
                blocks.append((number, last, value, grouped))
                consumed = end
        offset += len(line)
    return blocks


def tables(text: str, expected: dict[str, str]) -> tuple[list[dict], dict]:
    """Select the last complete table; reject inconsistent repeated complete tables."""
    lines = text.splitlines()
    candidates = []
    fragments = []
    for number, line in enumerate(lines):
        header = line.split("\t")
        if not {"id", "path", "state", "collected", "receipt_status"} <= set(header):
            continue
        rows = []
        for row_number in range(number + 1, len(lines)):
            values = lines[row_number].split("\t")
            if not values or values[0] not in expected:
                break
            if len(values) < len(header):
                break
            row = dict(zip(header, values, strict=False))
            row["_source_line"] = str(row_number + 1)
            if len(values) > len(header):
                row["_trailing_fields"] = values[len(header) :]
            rows.append(row)
        ids = [r["id"] for r in rows]
        complete = len(ids) == len(expected) and set(ids) == set(expected)
        fragments.append({"header_line": number + 1, "rows": len(rows), "complete": complete})
        if complete:
            require(len(ids) == len(set(ids)), "duplicate table IDs")
            for row in rows:
                require(row["path"] == expected[row["id"]], f"path drift: {row['id']}")
            candidates.append(rows)
    require(bool(candidates), "no complete table matching the assigned set")

    def clean(rows: list[dict]) -> list[dict]:
        return [{k: v for k, v in r.items() if k != "_source_line"} for r in rows]

    require(
        all(clean(x) == clean(candidates[-1]) for x in candidates), "complete-table disagreement"
    )
    return candidates[-1], {"tables": fragments, "selected": "last_complete_exact_manifest_set"}


def generate(root: Path) -> dict[str, str]:
    """Walk every planned job, transferred source, finding, and route."""
    allocation = json.loads((root.parent / "full-run/allocation.json").read_text())
    owners = list(
        csv.DictReader(
            (root.parent / "execution-organization/finding-owners.tsv").open(), delimiter="\t"
        )
    )
    routes = json.loads((root.parent / "full-run/finding-routes.json").read_text())["findings"]
    seeds = json.loads((root / "sources.json").read_text())["sources"]
    jobs = {j["id"]: j for j in allocation["jobs"]}
    require(len(seeds) == len(jobs), "source/job denominator drift")
    require({s["job"] for s in seeds} == set(jobs), "source/job set mismatch")
    require(len({s["job"] for s in seeds}) == len(seeds), "duplicate source job")
    all_cells, all_properties, events, gates, source_reports = [], [], [], [], []
    for source in sorted(seeds, key=lambda x: x["job"]):
        job = jobs[source["job"]]
        data = (root / source["path"]).read_bytes()
        require(
            hashlib.sha256(data).hexdigest() == source["sha256"], "transferred source hash drift"
        )
        text = data.decode("utf-8")
        blocks = json_blocks(text)
        metadata_blocks = [
            (first, last, x)
            for first, last, x, _ in blocks
            if isinstance(x, dict) and str(x.get("job", "")).endswith(job["id"])
        ]
        require(bool(metadata_blocks), f"metadata missing: {job['id']}")
        _, _, metadata = metadata_blocks[0]
        sha = metadata.get("source", metadata.get("source_sha"))
        require(sha == job["cut"]["sha"], f"cut drift: {job['id']}")
        require(metadata["tree"] == job["cut"]["tree"], f"tree drift: {job['id']}")
        require(
            metadata["manifest_sha256"] == job["inline_manifest_sha256"], "manifest binding drift"
        )
        for _, _, repeated in metadata_blocks:
            require(
                repeated.get("source", repeated.get("source_sha")) == sha
                and repeated["tree"] == metadata["tree"]
                and repeated["manifest_sha256"] == metadata["manifest_sha256"],
                "repeated metadata binding disagreement",
            )
        expected = {f["cell_id"]: f["path"] for f in job["files"]}
        require(len(expected) == len(job["files"]), "duplicate planned cell")
        primary, selection = tables(text, expected)
        extra_states = {p["state_id"]: p["path"] for p in job.get("property_states", [])}
        properties = tables(text, extra_states)[0] if extra_states else []
        for rows, destination in [(primary, all_cells), (properties, all_properties)]:
            for row in rows:
                output = {field: row.get(field, "null") for field in FIELDS}
                output.update(
                    job=job["id"],
                    source_sha=sha,
                    source_file=source["path"],
                    source_line=row["_source_line"],
                )
                extras = {k: v for k, v in row.items() if k not in FIELDS and k != "_source_line"}
                output["extra_json"] = compact(extras)
                destination.append(output)
        gate_by_id = {}

        def collect_gates(
            value: object,
            line_start: int,
            line_end: int,
            gate_by_id: dict = gate_by_id,
            job_id: str = job["id"],
            source_file: str = source["path"],
        ) -> None:
            if isinstance(value, dict):
                key = value.get("id")
                if isinstance(key, str) and re.fullmatch(r"G\d{2}", key) and "state" in value:
                    require(
                        key not in gate_by_id or gate_by_id[key]["state"] == value["state"],
                        "conflicting gate states",
                    )
                    gate_by_id[key] = {
                        "id": key,
                        "job": job_id,
                        "state": value["state"],
                        "source_file": source_file,
                        "line_start": line_start,
                        "line_end": line_end,
                        "reported": value,
                    }
                for item in value.values():
                    collect_gates(item, line_start, line_end)
            elif isinstance(value, list):
                for item in value:
                    collect_gates(item, line_start, line_end)

        for line_start, line_end, value, grouped in blocks:
            collect_gates(value, line_start, line_end)
            if isinstance(value, dict) and str(value.get("job", "")).endswith(job["id"]):
                continue
            cell_ids = sorted(cell_references(value))
            events.append(
                {
                    "job": job["id"],
                    "source_file": source["path"],
                    "line_start": line_start,
                    "line_end": line_end,
                    "kind": "message_node_group" if grouped else "json_block",
                    "cell_ids": cell_ids,
                    "keys": list(value) if isinstance(value, dict) else [],
                    "grade": "source_locator_not_normalized_failure_event",
                }
            )
        event_header: list[str] = []
        for number, line in enumerate(text.splitlines(), 1):
            values = line.split("\t")
            if {"cell", "phase", "outcome"} <= set(values):
                event_header = values
                continue
            if event_header and values[0] in expected and len(values) == len(event_header):
                events.append(
                    {
                        "job": job["id"],
                        "source_file": source["path"],
                        "line_start": number,
                        "line_end": number,
                        "kind": "tsv_event_row",
                        "cell_ids": [values[0]],
                        "keys": event_header,
                        "grade": "source_locator_not_normalized_failure_event",
                    }
                )
            elif event_header:
                event_header = []
        expected_gates = {g["id"] for g in job.get("gates", [])}
        require(set(gate_by_id) == expected_gates, f"gate set mismatch {job['id']}")
        gates.extend(gate_by_id.values())
        source_reports.append(
            {
                "job": job["id"],
                "source_sha": sha,
                "transferred_bytes": len(data),
                "source_sha256": source["sha256"],
                "metadata_lines": [[a, b] for a, b, _ in metadata_blocks],
                "primary_cells": len(primary),
                "states": dict(sorted(Counter(r["state"] for r in primary).items())),
                "properties": len(properties),
                "gates": len(gate_by_id),
                "table_selection": selection,
                "binding_grade": "recomputed_text_binding",
                "behavior_grade": "source_reported_compact_text_only",
                "raw_archive_transfer": "missing",
            }
        )
    require(
        len(all_cells) == allocation["denominators"]["native_python_cells"], "primary census drift"
    )
    require(len({r["id"] for r in all_cells}) == len(all_cells), "duplicate primary IDs")
    require(
        len(all_properties) == allocation["denominators"]["additional_property_replay_states"],
        "property census drift",
    )
    require(len(gates) == allocation["denominators"]["non_pytest_commands"], "gate census drift")
    by_id = {r["id"]: r for r in all_cells}
    owner_by_id = {r["finding_id"]: r for r in owners}
    require(len(owner_by_id) == len(owners) == len(routes), "finding denominator drift")
    require(set(owner_by_id) == {r["finding_id"] for r in routes}, "finding set drift")
    routed = []
    for finding in routes:
        fid = finding["finding_id"]
        basis = {
            "semantic_adequacy": finding["semantic_adequacy"],
            "canonical_route": "../full-run/finding-routes.json#" + fid,
        }
        count = 0
        for route in finding["assigned_routes"]:
            for cell_id in route["cell_ids"]:
                require(cell_id in by_id, f"unknown routed cell {cell_id}")
                cell = by_id[cell_id]
                require(
                    cell["job"] == route["job"] and jobs[route["job"]]["ref"] == route["ref"],
                    f"route cut mismatch {cell_id}",
                )
                routed.append(
                    {
                        "finding_id": fid,
                        "unit": owner_by_id[fid]["unit"],
                        "cell_id": cell_id,
                        "source_status": owner_by_id[fid]["source_status"],
                        "route_grade": finding["route_grade"],
                        "source_ref": route["ref"],
                        **basis,
                    }
                )
                count += 1
        if count == 0:
            routed.append(
                {
                    "finding_id": fid,
                    "unit": owner_by_id[fid]["unit"],
                    "cell_id": "",
                    "source_status": owner_by_id[fid]["source_status"],
                    "route_grade": "no_assigned_native_cell_semantic_test_missing",
                    "source_ref": "",
                    **basis,
                }
            )
    report = {
        "schema": "policyos.e02.transferred_results_index.v1",
        "scope": "15 transferred UTF-8 texts; 2074 planned Python file/cut cells",
        "sources": source_reports,
        "primary_cells": len(all_cells),
        "primary_states": dict(sorted(Counter(r["state"] for r in all_cells).items())),
        "property_states": len(all_properties),
        "gates": len(gates),
        "gate_states": dict(sorted(Counter(g["state"] for g in gates).items())),
        "finding_ids": len(owner_by_id),
        "route_rows": len(routed),
        "unrouted_findings": sorted(r["finding_id"] for r in routed if not r["cell_id"]),
        "locator_records": len(events),
        "raw_archives_received": 0,
        "index_acceptance": "transfer_and_navigation_only",
        "product_closure": "not_established",
    }
    return {
        "cells.tsv": tsv(all_cells, FIELDS),
        "properties.tsv": tsv(all_properties, FIELDS),
        "events.jsonl": "".join(compact(x) + "\n" for x in events),
        "gates.json": compact(sorted(gates, key=lambda x: x["id"])) + "\n",
        "routes.tsv": tsv(
            routed,
            [
                "finding_id",
                "unit",
                "cell_id",
                "source_status",
                "route_grade",
                "source_ref",
                "semantic_adequacy",
                "canonical_route",
            ],
        ),
        "verification.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    }


def main() -> int:
    """Regenerate or compare every derived artifact against its transferred inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        outputs = generate(args.root)
        for name, value in outputs.items():
            path = args.root / name
            if args.write:
                path.write_text(value)
            else:
                require(path.read_text() == value, f"derived artifact drift: {name}")
        sys.stdout.write(compact({"ok": True, "files": list(outputs)}) + "\n")
    except (ValueError, KeyError, OSError) as error:
        sys.stderr.write(f"index verification failed: {error}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
