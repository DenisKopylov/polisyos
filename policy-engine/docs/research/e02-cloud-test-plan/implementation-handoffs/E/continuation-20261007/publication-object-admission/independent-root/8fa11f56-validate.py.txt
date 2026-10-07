"""Recompute Git footprint and published deciding-output integrity for this receipt."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["/usr/bin/git", *args], cwd=repo)  # noqa: S603 - Fixed read-only Git calls.


def validate(repo: Path, receipt: dict) -> None:
    """Reject source/footprint/asset claims that do not reproduce from actual inputs."""
    candidate = receipt["implementation_commits"][-1]
    tree = _git(repo, "rev-parse", f"{candidate}^{{tree}}").decode().strip()
    if tree != receipt["candidate_tree_sha"]:
        raise ValueError("candidate tree mismatch")
    actual = set(
        _git(repo, "diff", "--name-only", receipt["slice_base_sha"], candidate)
        .decode()
        .splitlines()
    )
    declared = {row["path"] for row in receipt["footprint"]}
    if declared != actual or set(receipt["changed_paths"]) != actual:
        raise ValueError("incomplete changed footprint")
    for row in receipt["footprint"]:
        data = _git(repo, "show", f"{candidate}:{row['path']}")
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("source postimage mismatch")
        blob = _git(repo, "rev-parse", f"{candidate}:{row['path']}").decode().strip()
        if blob != row["candidate_blob"]:
            raise ValueError("source Git blob mismatch")
    if not receipt["assets"]:
        raise ValueError("missing deciding outputs")
    for row in receipt["assets"]:
        path = (repo / row["path"]).resolve()
        if not path.is_relative_to(repo.resolve()):
            raise ValueError("asset outside repository")
        data = path.read_bytes()
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("deciding output mismatch")


def main() -> None:
    """Check the real receipt and execute independent corrupt-field refusals."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text())
    validate(args.repo_root, receipt)
    controls = {}
    for name in ("tree", "source_hash", "missing_path", "asset_hash", "outside_path"):
        damaged = copy.deepcopy(receipt)
        if name == "tree":
            damaged["candidate_tree_sha"] = "0" * 40
        elif name == "source_hash":
            damaged["footprint"][0]["sha256"] = "0" * 64
        elif name == "missing_path":
            damaged["footprint"].pop()
        elif name == "asset_hash":
            damaged["assets"][0]["sha256"] = "0" * 64
        else:
            damaged["assets"][0]["path"] = str(
                args.repo_root.resolve().parent / "outside-repository"
            )
        try:
            validate(args.repo_root, damaged)
        except ValueError as exc:
            controls[name] = str(exc)
        else:
            raise AssertionError(f"corrupt-field control admitted: {name}")
    sys.stdout.write(
        json.dumps({"receipt_check": "PASS", "corrupt_field_refusals": controls}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
