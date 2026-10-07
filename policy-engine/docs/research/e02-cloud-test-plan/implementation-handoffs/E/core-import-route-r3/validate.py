"""Recompute Git footprint and published deciding-output integrity for this receipt."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["/usr/bin/git", *args], cwd=repo)  # noqa: S603 - fixed Git verbs; complete source/asset record is admitted before callbacks.


def _admit_hash(value: object, length: int) -> None:
    if not isinstance(value, str) or re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is None:
        raise ValueError("source identity must be an exact hexadecimal hash")


def _admit_path(value: object) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError("source path must be a canonical repository-relative string")
    relative = Path(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or value != relative.as_posix()
        or value.startswith("-")
        or ":" in value
        or any(character.isspace() or character == "\0" for character in value)
    ):
        raise ValueError("source path must be canonical and repository relative")


def _admit_receipt(receipt: dict, publication_revision: str | None) -> None:
    commits = receipt["implementation_commits"]
    if not isinstance(commits, list) or not commits:
        raise ValueError("receipt must name implementation commits")
    for commit in commits:
        _admit_hash(commit, 40)
    _admit_hash(receipt["slice_base_sha"], 40)
    _admit_hash(receipt["candidate_tree_sha"], 40)
    if publication_revision is not None:
        _admit_hash(publication_revision, 40)
    for name in ("footprint", "assets"):
        records = receipt[name]
        if not isinstance(records, list) or not records:
            raise ValueError("receipt must contain the complete source and asset sets")
        paths = []
        for record in records:
            _admit_path(record["path"])
            paths.append(record["path"])
            if type(record["bytes"]) is not int or record["bytes"] < 0:
                raise ValueError("source/asset size must be a nonnegative integer")
            _admit_hash(record["sha256"], 64)
            if name == "footprint":
                _admit_hash(record["candidate_blob"], 40)
        if len(paths) != len(set(paths)):
            raise ValueError("duplicate source/asset path")
    paths = receipt["changed_paths"]
    if not isinstance(paths, list):
        raise ValueError("changed paths must be a complete list")
    for path in paths:
        _admit_path(path)
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate changed path")


def validate(repo: Path, receipt: dict, publication_revision: str | None = None) -> None:
    """Reject source/footprint/asset claims that do not reproduce from actual inputs."""
    _admit_receipt(receipt, publication_revision)
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
        data = (
            path.read_bytes()
            if publication_revision is None
            else _git(repo, "show", f"{publication_revision}:{row['path']}")
        )
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("deciding output mismatch")


def main() -> None:
    """Check the real receipt and execute independent corrupt-field refusals."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument(
        "--publication-revision",
        help="Exact historical commit for asset replay; default checks current copies",
    )
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text())
    validate(args.repo_root, receipt, args.publication_revision)
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
            validate(args.repo_root, damaged, args.publication_revision)
        except ValueError as exc:
            controls[name] = str(exc)
        else:
            raise AssertionError(f"corrupt-field control admitted: {name}")
    sys.stdout.write(
        json.dumps({"receipt_check": "PASS", "corrupt_field_refusals": controls}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
