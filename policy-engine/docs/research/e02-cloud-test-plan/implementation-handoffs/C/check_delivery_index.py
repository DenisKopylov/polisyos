"""Recompute C inventory and Git identities; this does not admit finding closure."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path


def require(condition: bool, detail: object) -> None:
    """Reject drift even when Python assertions are disabled."""
    if not condition:
        raise ValueError(f"delivery index drift: {detail}")


def git_bytes(root: Path, *args: str) -> bytes:
    """Read Git objects with a resolved executable and no shell."""
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is unavailable")
    require(args[0] in {"rev-parse", "show", "diff", "merge-base", "ls-remote"}, args[0])
    # Only read operations; the committed index supplies object and ref arguments.
    return subprocess.check_output([executable, *args], cwd=root)  # noqa: S603


def git(root: Path, *args: str) -> str:
    """Read a Git object or identity from the calling checkout."""
    return git_bytes(root, *args).decode().strip()


def check(index_path: Path, *, remote: bool) -> dict[str, object]:
    """Reconcile the complete owned set and all pinned slice receipts."""
    root = Path(git(index_path.parent, "rev-parse", "--show-toplevel"))
    index = json.loads(index_path.read_text())
    require(index["schema"] == "policyos.e02.C_delivery_index.v1", "index schema differs")
    source_cut = index["source_cut"]
    loaded = {}
    for key, ref in index["source_paths"].items():
        data = git_bytes(root, "show", f"{source_cut}:{ref['path']}")
        require(hashlib.sha256(data).hexdigest() == ref["sha256"], key)
        loaded[key] = data.decode()
    owners = list(csv.DictReader(loaded["finding_owners"].splitlines(), delimiter="\t"))
    bundles = list(csv.DictReader(loaded["bundle_owners"].splitlines(), delimiter="\t"))
    cells = list(csv.DictReader(loaded["cells"].splitlines(), delimiter="\t"))
    routes = list(csv.DictReader(loaded["routes"].splitlines(), delimiter="\t"))
    ledger = json.loads(loaded["ledger"])["rows"]
    owned = {row["finding_id"]: row for row in owners if row["unit"] == "C"}
    owned_bundles = {row["bundle_id"] for row in bundles if row["unit"] == "C"}
    ledger_by_id = {row["id"]: row for row in ledger}
    c_routes = [row for row in routes if row["finding_id"] in owned]
    cell_ids = {row["cell_id"] for row in c_routes}
    cell_by_id = {row["id"]: row for row in cells}
    statuses = Counter(ledger_by_id[key]["status"] for key in owned)
    denominator = {
        "bundle_owner_rows": len(bundles),
        "C_bundles": len(owned_bundles),
        "finding_owner_rows": len(owners),
        "C_findings": len(owned),
        "ledger_rows": len(ledger),
        "result_cells_rows": len(cells),
        "result_routes_rows": len(routes),
        "C_route_links": len(c_routes),
        "C_distinct_cells": len(cell_ids),
        "C_cell_states": dict(Counter(cell_by_id[key]["state"] for key in cell_ids)),
        "C_ledger_states": dict(statuses),
    }
    require(denominator == index["denominator"], "denominator differs from complete source walk")
    require(
        sorted({row["route_grade"] for row in c_routes})
        == index["baseline_limits"]["route_grades"],
        "baseline route grades differ",
    )
    require(
        sorted({row["semantic_adequacy"] for row in c_routes})
        == index["baseline_limits"]["semantic_adequacy"],
        "baseline semantic adequacy differs",
    )
    require(
        sorted(key for key in cell_ids if cell_by_id[key]["state"] == "FAILED")
        == index["baseline_limits"]["original_failed_cells"],
        "baseline failed cell set differs",
    )
    require(set(index["bundle_dispositions"]) == owned_bundles, "bundle set differs")
    records = index["findings"]
    require(len(records) == len(owned), "finding cardinality differs")
    require({row["id"] for row in records} == set(owned), "finding set differs")
    require(all(row["unit"] == "C" for row in c_routes), "route owner mismatch")
    for row in records:
        source = owned[row["id"]]
        require(row["source_status"] == source["source_status"], row["id"])
        require(row["ledger_status"] == ledger_by_id[row["id"]]["status"], row["id"])
        require(row["bundle_ids"] == source["source_bundle_ids"].split(","), row["id"])
        expected_refs = {
            key
            for bundle in row["bundle_ids"]
            for key in index["bundle_dispositions"][bundle]["slice_refs"]
        }
        require(set(row["slice_refs"]) == expected_refs, row["id"])
        for key in row["slice_refs"]:
            require(key in index["slices"], (row["id"], key))
    required = {
        "schema",
        "unit",
        "slice",
        "closure_ids",
        "bundle_ids",
        "slice_base_sha",
        "implementation_commits",
        "candidate_tree_sha",
        "branch",
        "pull_request",
        "changed_paths",
        "baseline_cells",
        "checks",
        "property",
        "predicate_basis",
        "capability_state_or_finding_state",
        "limitations_and_next_owner",
    }
    receipt_bundle_refs: dict[str, set[str]] = {bundle: set() for bundle in owned_bundles}
    for key, entry in index["slices"].items():
        require(entry["slice_base_sha"] == source_cut, (key, "C slice source cut differs"))
        head = entry["head_sha"]
        receipt = json.loads(git(root, "show", f"{head}:{entry['receipt_path']}"))
        require(required <= receipt.keys(), key)
        require(receipt["schema"] == "policyos.e02.implementation_handoff.v1", key)
        require(receipt["unit"] == "C" and receipt["branch"] == entry["branch"], key)
        require(receipt["slice"] == entry["receipt_slice"], (key, "receipt slice differs"))
        require(receipt["slice_base_sha"] == entry["slice_base_sha"], (key, "slice base differs"))
        require(set(receipt["closure_ids"]) <= set(owned), (key, "unowned finding"))
        require(
            {"statement", "runtime_path", "proxy_divergence", "negative_controls"}
            <= receipt["property"].keys(),
            key,
        )
        require(receipt["implementation_commits"] == entry["implementation_commits"], key)
        require(receipt["candidate_tree_sha"] == entry["candidate_tree_sha"], key)
        require(set(receipt["bundle_ids"]) <= owned_bundles, key)
        for bundle in receipt["bundle_ids"]:
            receipt_bundle_refs[bundle].add(key)
        implementation = receipt["implementation_commits"][-1]
        require(
            git(root, "rev-parse", f"{implementation}^{{tree}}") == entry["candidate_tree_sha"], key
        )
        for commit in [receipt["slice_base_sha"], *receipt["implementation_commits"]]:
            git(root, "merge-base", "--is-ancestor", commit, head)
        changed = set(
            git(root, "diff", "--name-only", receipt["slice_base_sha"], implementation).splitlines()
        )
        mechanism = {path for path in changed if "/implementation-handoffs/" not in path}
        require(mechanism <= set(receipt["changed_paths"]), key)
    for bundle, disposition in index["bundle_dispositions"].items():
        require(set(disposition["slice_refs"]) == receipt_bundle_refs[bundle], bundle)
    if remote:
        expected = {
            f"refs/heads/{entry['branch']}": entry["head_sha"] for entry in index["slices"].values()
        }
        actual = dict(
            line.split()[::-1]
            for line in git(
                root, "ls-remote", "--heads", "origin", "refs/heads/codex/e02-C-*"
            ).splitlines()
            if line.split()[1] != f"refs/heads/{index['report_branch']}"
        )
        require(actual == expected, "remote head differs")
    return {
        "outcome": "PASS",
        "scope": "inventory and pinned Git identities only",
        "denominator": denominator,
        "implementation_slices": len(index["slices"]),
        "remote_checked": remote,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index", type=Path, default=Path(__file__).with_name("delivery-index.json")
    )
    parser.add_argument("--remote", action="store_true")
    args = parser.parse_args()
    sys.stdout.write(
        json.dumps(check(args.index.resolve(), remote=args.remote), sort_keys=True) + "\n"
    )
