"""Recompute the complete E02-A baseline denominator from immutable Git inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
from collections import Counter


def main() -> None:
    """Walk complete source tables and check every received-source digest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-ref", required=True)
    args = parser.parse_args()
    git_path = shutil.which("git")
    if git_path is None:
        raise RuntimeError("Git executable unavailable")
    root = subprocess.check_output(  # noqa: S603 - resolved Git, constant read-only command
        [git_path, "rev-parse", "--show-toplevel"], text=True
    ).strip()
    # Read-only Git revision; argument vector never invokes a shell.
    source_sha = subprocess.check_output(  # noqa: S603
        [git_path, "rev-parse", "--verify", "--end-of-options", args.source_ref + "^{commit}"],
        cwd=root,
        text=True,
    ).strip()
    prefix = "policy-engine/docs/research/e02-cloud-test-plan/"

    def read(path: str) -> bytes:
        return subprocess.check_output([git_path, "show", f"{source_sha}:{prefix}{path}"], cwd=root)  # noqa: S603

    def table(path: str) -> list[dict[str, str]]:
        return list(csv.DictReader(io.StringIO(read(path).decode()), delimiter="\t"))

    bundles = table("execution-organization/bundle-owners.tsv")
    findings = table("execution-organization/finding-owners.tsv")
    cells = table("results/cells.tsv")
    routes = table("results/routes.tsv")
    properties = table("results/properties.tsv")
    events = [json.loads(line) for line in read("results/events.jsonl").splitlines()]
    sources = json.loads(read("results/sources.json"))["sources"]
    for source in sources:
        payload = read("results/" + source["path"])
        if hashlib.sha256(payload).hexdigest() != source["sha256"]:
            raise ValueError(f"received-source hash mismatch: {source['path']}")
    a_bundles = [row for row in bundles if row["unit"] == "A"]
    a_findings = [row for row in findings if row["unit"] == "A"]
    a_routes = [row for row in routes if row["unit"] == "A"]
    cell_ids = {row["cell_id"] for row in a_routes}
    a_cells = [row for row in cells if row["id"] in cell_ids]
    if len(a_cells) != len(cell_ids):
        raise ValueError("A route/cell join is incomplete")
    summary = {
        "source_sha": source_sha,
        "complete_file_denominator": {
            "bundle-owners.tsv": len(bundles),
            "finding-owners.tsv": len(findings),
            "cells.tsv": len(cells),
            "routes.tsv": len(routes),
            "properties.tsv": len(properties),
            "events.jsonl": len(events),
            "sources.json received text files": len(sources),
        },
        "A": {
            "bundles": len(a_bundles),
            "findings": len(a_findings),
            "routes": len(a_routes),
            "unique_cells": len(a_cells),
            "unique_test_paths": len({row["path"] for row in a_cells}),
            "finding_status": dict(Counter(row["source_status"] for row in a_findings)),
            "cell_status": dict(Counter(row["state"] for row in a_cells)),
        },
    }
    sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
