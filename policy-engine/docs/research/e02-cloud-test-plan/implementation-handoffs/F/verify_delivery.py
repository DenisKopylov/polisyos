"""Recompute F delivery bookkeeping from exact Git objects, without product claims."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[6]
GIT = shutil.which("git")
if GIT is None:
    raise RuntimeError("git is required")
OWNER_ROOT = "policy-engine/docs/research/e02-cloud-test-plan/execution-organization"


def git(*args: str) -> bytes:
    """Read local Git objects; callers must fetch the pinned topic heads first."""
    return subprocess.check_output([GIT, "-C", str(ROOT), *args])  # noqa: S603 - fixed Git commands and validated object IDs; no shell


def rows_at(base: str, name: str) -> list[dict[str, str]]:
    """Read every owner row from its immutable source version."""
    raw = git("show", f"{base}:{OWNER_ROOT}/{name}").decode()
    return list(csv.DictReader(io.StringIO(raw), delimiter="\t"))


def require(condition: bool, message: str) -> None:
    """Reject an unbound declaration even when Python runs with optimization."""
    if not condition:
        raise ValueError(message)


def object_id(value: str) -> None:
    """Admit only immutable full Git object identifiers, never option strings."""
    require(re.fullmatch(r"[0-9a-f]{40}", value) is not None, "invalid Git object ID")


def ancestor(older: str, newer: str) -> None:
    """Check ancestry using already validated immutable object identifiers."""
    object_id(older)
    object_id(newer)
    git("merge-base", "--is-ancestor", older, newer)


def content_refs(value: object, head: str, unadmitted: list[dict[str, str]]) -> int:
    """Recompute every declared Git path/hash pair; local raw stays unadmitted."""
    count = 0
    if isinstance(value, dict):
        path = value.get("path")
        if isinstance(path, str) and path.startswith("policy-engine/") and "sha256" in value:
            if "/raw/" in path and str(value.get("transfer", "")).startswith("local"):
                unadmitted.append(
                    {
                        "path": path,
                        "sha256": value["sha256"],
                        "basis": "not_established; local declaration only",
                    }
                )
                return 0
            raw = git("show", f"{head}:{path}")
            require(hashlib.sha256(raw).hexdigest() == value["sha256"], path + " hash")
            require(len(raw) == value.get("bytes", len(raw)), path + " byte count")
            count += 1
        for child in value.values():
            count += content_refs(child, head, unadmitted)
    elif isinstance(value, list):
        for child in value:
            count += content_refs(child, head, unadmitted)
    return count


def verify(index: dict[str, Any]) -> dict[str, Any]:
    """Bind the full F denominator and slice receipts, not scientific predicates."""
    require(index["unit"] == "F", "wrong unit")
    base = index["source_base_sha"]
    object_id(base)
    bundles = rows_at(base, "bundle-owners.tsv")
    findings = rows_at(base, "finding-owners.tsv")
    expected_bundles = {r["bundle_id"] for r in bundles if r["unit"] == "F"}
    expected_findings = {r["finding_id"] for r in findings if r["unit"] == "F"}
    require(len(expected_bundles) == 17 and len(expected_findings) == 35, "owner denominator")
    require(len(index["bundle_ids"]) == 17, "bundle uniqueness")
    require(set(index["bundle_ids"]) == expected_bundles, "bundle union")
    admitted = [r["finding_id"] for r in index["finding_residuals"]]
    require(len(admitted) == len(set(admitted)) == 35, "finding uniqueness")
    require(set(admitted) == expected_findings, "finding union")
    ownership = {r["finding_id"]: r for r in findings if r["unit"] == "F"}
    for row in index["finding_residuals"]:
        source = ownership[row["finding_id"]]
        require(row["closure_owner"] == source["source_closure_owner"], "finding owner")
        require(row["ledger_status_preserved"] == source["source_status"], "finding source status")
        require(set(row["bundle_ids"]) == set(source["source_bundle_ids"].split(",")), "membership")
        require(
            row["candidate_semantic_state"]
            in {"limited_no_ledger_closure", "limited_principal_decision_pending", "held"},
            "candidate finding promoted by declaration",
        )
        if row["finding_id"] == "B219":
            require(row["candidate_semantic_state"] == "held", "B219 remains held")
    require(index["accepted_finding_closures"] == [], "finding closure not authorized")
    require(index["integration_acceptance"] == "pending_G", "integration not accepted")
    index_raw: list[dict[str, str]] = []
    index_refs = content_refs(index, git("rev-parse", "HEAD").decode().strip(), index_raw)
    seen_branches: set[str] = set()
    product_footprints: list[set[str]] = []
    evidence = []
    for item in index["slices"]:
        branch, head = item["branch"], item["published_head_sha"]
        require(branch.startswith("codex/e02-F-") and branch not in seen_branches, "branch scope")
        object_id(head)
        seen_branches.add(branch)
        require(git("rev-parse", head).decode().strip() == head, "missing exact object")
        ancestor(base, head)
        raw = git("show", f"{head}:{item['receipt_path']}")
        require(hashlib.sha256(raw).hexdigest() == item["receipt_sha256"], "receipt hash")
        require(len(raw) == item["receipt_bytes"], "receipt byte count")
        receipt = json.loads(raw)
        require(receipt["schema"] == "policyos.e02.implementation_handoff.v1", "receipt schema")
        require(receipt["unit"] == "F" and receipt["branch"] == branch, "receipt scope")
        require(receipt["slice_base_sha"] == base, "slice base")
        require(item["candidate_tree_sha"] == receipt["candidate_tree_sha"], "index candidate tree")
        commits = receipt["implementation_commits"]
        require(
            commits == item["implementation_commits"] and bool(commits), "implementation commits"
        )
        for commit in commits:
            object_id(commit)
        require(
            git("rev-parse", f"{commits[-1]}^{{tree}}").decode().strip()
            == receipt["candidate_tree_sha"],
            "candidate tree",
        )
        paths: set[str] = set()
        for commit in commits:
            ancestor(commit, head)
            paths.update(
                git("diff-tree", "--no-commit-id", "--name-only", "-r", commit)
                .decode()
                .splitlines()
            )
        require(paths == set(receipt["changed_paths"]), branch + " implementation footprint")
        later = git("diff", "--name-only", commits[-1], head).decode().splitlines()
        require(
            not any(
                path.startswith(("policy-engine/src/", "policy-engine/tests/")) for path in later
            ),
            branch + " source changed after frozen implementation",
        )
        unadmitted: list[dict[str, str]] = []
        bound_refs = content_refs(receipt, head, unadmitted)
        product_footprints.append(paths)
        evidence.append(
            {
                "branch": branch,
                "head": head,
                "implementation_paths": len(paths),
                "bound_output_refs": bound_refs,
                "unadmitted_relative_raw_refs": unadmitted,
            }
        )
    require(len(seen_branches) == 9, "slice count")
    for i, paths in enumerate(product_footprints):
        for other in product_footprints[i + 1 :]:
            require(not paths.intersection(other), "conflicting slice writers")
    return {
        "outcome": "PASS",
        "scope": "Git/source/owner bookkeeping only; product acceptance not established",
        "F_bundles": 17,
        "F_findings": 35,
        "slices": evidence,
        "accepted_finding_closures": [],
        "bound_index_companion_refs": index_refs,
        "unadmitted_index_raw_refs": index_raw,
    }


def main() -> None:
    """Validate an index, optionally run declaration-preserving negative controls."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--negative-controls", action="store_true")
    args = parser.parse_args()
    index = json.loads(args.index.read_text())
    result = verify(index)
    if args.negative_controls:
        mutants = []
        duplicate = json.loads(json.dumps(index))
        duplicate["finding_residuals"][-1] = duplicate["finding_residuals"][0]
        mutants.append(("35 rows with one missing finding and a duplicate", duplicate))
        forged = json.loads(json.dumps(index))
        forged["slices"][0]["receipt_sha256"] = "0" * 64
        mutants.append(("right branch and head with an unbound receipt", forged))
        promoted = json.loads(json.dumps(index))
        promoted["accepted_finding_closures"] = ["B219"]
        mutants.append(("held finding promoted by declaration", promoted))
        duplicate_bundle = json.loads(json.dumps(index))
        duplicate_bundle["bundle_ids"].append(duplicate_bundle["bundle_ids"][0])
        mutants.append(("right bundle union with a duplicate row", duplicate_bundle))
        wrong_owner = json.loads(json.dumps(index))
        wrong_owner["finding_residuals"][0]["closure_owner"] = "invented-owner"
        mutants.append(("35 IDs with a false owner", wrong_owner))
        closed_row = json.loads(json.dumps(index))
        closed_row["finding_residuals"][0]["candidate_semantic_state"] = "closed"
        mutants.append(("empty closure list hiding a closed finding row", closed_row))
        wrong_companion = json.loads(json.dumps(index))
        wrong_companion["independent_companions"][0]["sha256"] = "0" * 64
        mutants.append(("right slices with an unbound index companion", wrong_companion))
        stale_receipt = json.loads(json.dumps(index))
        for item in stale_receipt["slices"]:
            if item["branch"] == "codex/e02-F-lex":
                item["published_head_sha"] = "56aa7d47876b29956676ef8dc9f04b64c865948f"
                raw = git("show", f"{item['published_head_sha']}:{item['receipt_path']}")
                old = json.loads(raw)
                item["receipt_sha256"] = hashlib.sha256(raw).hexdigest()
                item["receipt_bytes"] = len(raw)
                item["implementation_commits"] = old["implementation_commits"]
                item["candidate_tree_sha"] = old["candidate_tree_sha"]
        mutants.append(("real source changed after a still-valid old receipt", stale_receipt))
        rejected = []
        for name, mutant in mutants:
            try:
                verify(mutant)
            except ValueError as exc:
                if name == "real source changed after a still-valid old receipt":
                    require(
                        "source changed after frozen" in str(exc), "wrong negative precondition"
                    )
                rejected.append({"control": name, "reason": str(exc)})
            else:
                raise ValueError(f"control was not rejected: {name}")
        result["negative_controls_rejected"] = rejected
    sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
