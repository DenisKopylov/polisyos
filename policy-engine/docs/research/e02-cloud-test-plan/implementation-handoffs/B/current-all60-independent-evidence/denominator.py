"Read immutable B allocation/cards/baseline navigation; never run product checks."

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import subprocess
import sys
from collections import Counter

ROOT_SHA = "99af508a5282854f3e609c5a94bc19ac55893dde"
CARD_SHA = "69780761ae091d8fcc6ab8778c7f5f7227eeef0b"
PLAN = "policy-engine/docs/research/e02-cloud-test-plan/"
CARDS = (
    "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/"
)


def blob(ref: str, path: str) -> bytes:
    # Fixed Git executable and immutable repository metadata arguments; no shell.
    return subprocess.check_output(["/usr/local/bin/git", "show", f"{ref}:{path}"])  # noqa: S603


def identity(ref: str, path: str) -> dict:
    raw = blob(ref, path)
    return {
        "git_sha": ref,
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def table(name: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(blob(ROOT_SHA, PLAN + name).decode()), delimiter="\t"))


def main() -> None:
    findings = table("execution-organization/finding-owners.tsv")
    bundles = table("execution-organization/bundle-owners.tsv")
    owned = [row for row in findings if row["unit"] == "B"]
    owned_bundles = [row for row in bundles if row["unit"] == "B"]
    if not len(findings) == len({row["finding_id"] for row in findings}) == 282:
        raise ValueError("metadata invariant failed")
    if not len(bundles) == len({row["bundle_id"] for row in bundles}) == 127:
        raise ValueError("metadata invariant failed")
    if not len(owned) == len({row["finding_id"] for row in owned}) == 60:
        raise ValueError("metadata invariant failed")
    if not len(owned_bundles) == len({row["bundle_id"] for row in owned_bundles}) == 25:
        raise ValueError("metadata invariant failed")
    expected = {row["finding_id"] for row in owned}
    criteria = {}
    cards = []
    for row in owned_bundles:
        path = CARDS + row["bundle_id"] + ".md"
        text = blob(CARD_SHA, path).decode()
        cards.append(identity(CARD_SHA, path))
        for match in re.finditer(
            ("<!-- SOURCE_BEGIN (?:B|LA):([^ ]+) -->(.*?)<!-- SOURCE_END (?:B|LA):\\1 -->"),
            text,
            re.S,
        ):
            finding = match[1]
            if finding not in expected:
                continue
            if not finding not in criteria:
                raise ValueError((finding, "split/duplicate canonical source"))
            criteria[finding] = {
                "bundle_id": row["bundle_id"],
                "path": path,
                "git_sha": CARD_SHA,
                "line_begin": text[: match.start()].count("\n") + 1,
                "line_end": text[: match.end()].count("\n") + 1,
                "source_block_sha256": hashlib.sha256(match[2].encode()).hexdigest(),
            }
    if not set(criteria) == expected:
        raise ValueError("metadata invariant failed")
    for row in owned:
        if not criteria[row["finding_id"]]["bundle_id"] == row["source_closure_owner"]:
            raise ValueError("metadata invariant failed")
    routes = json.loads(blob(ROOT_SHA, PLAN + "full-run/finding-routes.json"))["findings"]
    routes = {row["finding_id"]: row for row in routes if row["finding_id"] in expected}
    if not set(routes) == expected:
        raise ValueError("metadata invariant failed")
    cells = {row["id"]: row for row in table("results/cells.tsv")}
    selected = {
        cell
        for row in routes.values()
        for route in row["assigned_routes"]
        for cell in route["cell_ids"]
    }
    if not selected <= set(cells):
        raise ValueError("metadata invariant failed")
    events = [
        json.loads(line)
        for line in blob(ROOT_SHA, PLAN + "results/events.jsonl").decode().splitlines()
    ]
    jobs = sorted({cells[cell]["job"] for cell in selected})
    sources = json.loads(blob(ROOT_SHA, PLAN + "results/sources.json"))["sources"]
    source_by_job = {row["job"]: row for row in sources}
    for job in jobs:
        declared = source_by_job[job]
        actual = identity(ROOT_SHA, PLAN + "results/" + declared["path"])
        if not (actual["sha256"] == declared["sha256"] and actual["bytes"] == declared["bytes"]):
            raise ValueError("metadata invariant failed")
    output = {
        "schema": "polisyos.e02.B.independent.denominator.v1",
        "root_source_sha": ROOT_SHA,
        # Fixed Git executable and immutable repository metadata arguments; no shell.
        "root_source_tree": subprocess.check_output(  # noqa: S603
            ["/usr/local/bin/git", "rev-parse", ROOT_SHA + "^{tree}"], text=True
        ).strip(),
        "input_identities": [
            identity(ROOT_SHA, PLAN + name)
            for name in (
                "execution-organization/finding-owners.tsv",
                "execution-organization/bundle-owners.tsv",
                "full-run/finding-routes.json",
                "results/cells.tsv",
                "results/events.jsonl",
                "results/sources.json",
            )
        ],
        "counts": {
            "all_findings": 282,
            "all_bundles": 127,
            "B_findings": 60,
            "B_bundles": 25,
            "unique_baseline_cells": len(selected),
            "baseline_jobs": len(jobs),
            "source_statuses": dict(Counter(row["source_status"] for row in owned)),
            "foreign_findings": 0,
            "missing_criteria": 0,
            "split_criteria": 0,
        },
        "cards": cards,
        "findings": [
            {
                **row,
                "criterion": criteria[row["finding_id"]],
                "baseline_cell_ids": sorted(
                    {
                        cell
                        for route in routes[row["finding_id"]]["assigned_routes"]
                        for cell in route["cell_ids"]
                    }
                ),
            }
            for row in owned
        ],
        "baseline_cells": [cells[cell] for cell in sorted(selected)],
        "baseline_job_context_locators": [
            event for event in events if event["job"] in jobs and (not event["cell_ids"])
        ],
        "baseline_cell_source_locators": [
            event for event in events if selected.intersection(event["cell_ids"])
        ],
        "baseline_transfers": [source_by_job[job] for job in jobs],
        "limitations": [
            (
                "Baseline cells/source text are navigation and "
                "historical observations, never evidence of a new fix."
            ),
            (
                "Raw baseline archives absent; environment/input "
                "authority is only the pinned exact job-context/source "
                "locator, not reconstructed execution."
            ),
            (
                "This script verifies allocation/provenance counts only;"
                " it does not test runtime properties or close findings."
            ),
        ],
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("" + "\n")


if __name__ == "__main__":
    main()
